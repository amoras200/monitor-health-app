from pydantic import BaseModel, Field, HttpUrl


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    url: HttpUrl
