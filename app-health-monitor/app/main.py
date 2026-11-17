"""API FastAPI: cadastro de serviços e consulta de status."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from bson import ObjectId
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Response, status
from pymongo.errors import DuplicateKeyError

from app.config import MIN_API_KEY_LENGTH, get_settings
from app.db import ensure_indexes, get_db
from app.models import ServiceCreate
from app.security import UnsafeURLError, require_api_key, validate_public_url


@asynccontextmanager
async def lifespan(_: FastAPI):
    if len(get_settings().api_key) < MIN_API_KEY_LENGTH:
        raise RuntimeError(f"API_KEY precisa ter pelo menos {MIN_API_KEY_LENGTH} caracteres")
    ensure_indexes(get_db())
    yield


app = FastAPI(title="App Health Monitor", version="0.1.0", lifespan=lifespan)
router = APIRouter(dependencies=[Depends(require_api_key)])


def _parse_id(service_id: str) -> ObjectId:
    if not ObjectId.is_valid(service_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Serviço não encontrado")
    return ObjectId(service_id)


def _serialize(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "url": doc["url"],
        "state": doc.get("state", "unknown"),
        "consecutive_failures": doc.get("consecutive_failures", 0),
        "last_check_at": doc.get("last_check_at"),
        "created_at": doc.get("created_at"),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/services", status_code=status.HTTP_201_CREATED)
def create_service(payload: ServiceCreate) -> dict:
    url = str(payload.url)
    try:
        validate_public_url(url, get_settings().allow_private_targets)
    except UnsafeURLError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"URL não permitida: {exc}")

    doc = {
        "name": payload.name,
        "url": url,
        "state": "unknown",
        "consecutive_failures": 0,
        "created_at": datetime.now(UTC),
    }
    try:
        get_db().services.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Essa URL já está cadastrada")
    return _serialize(doc)


@router.get("/services")
def list_services() -> list[dict]:
    return [_serialize(doc) for doc in get_db().services.find({}).sort("name", 1)]


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(service_id: str) -> Response:
    oid = _parse_id(service_id)
    db = get_db()
    if db.services.delete_one({"_id": oid}).deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Serviço não encontrado")
    db.checks.delete_many({"service_id": oid})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/services/{service_id}/status")
def service_status(service_id: str) -> dict:
    oid = _parse_id(service_id)
    db = get_db()
    service = db.services.find_one({"_id": oid})
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Serviço não encontrado")

    since = datetime.now(UTC) - timedelta(hours=24)
    pipeline = [
        {"$match": {"service_id": oid, "ts": {"$gte": since}}},
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "ok": {"$sum": {"$cond": ["$ok", 1, 0]}},
                "avg_ms": {"$avg": {"$cond": ["$ok", "$response_ms", None]}},
            }
        },
    ]
    stats = next(iter(db.checks.aggregate(pipeline)), None)
    total = stats["total"] if stats else 0
    uptime = round(stats["ok"] / total * 100, 2) if total else None
    avg_ms = round(stats["avg_ms"]) if stats and stats["avg_ms"] is not None else None

    return {
        **_serialize(service),
        "last_24h": {"checks": total, "uptime_percent": uptime, "avg_response_ms": avg_ms},
    }


app.include_router(router)
