#!/usr/bin/env sh
# Gera um certificado AUTOASSINADO apenas para desenvolvimento local.
# Em produção, use um certificado de verdade (ex.: Let's Encrypt).
set -eu
mkdir -p nginx/certs
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout nginx/certs/key.pem -out nginx/certs/cert.pem \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
chmod 600 nginx/certs/key.pem
echo "Certificado gerado em nginx/certs/"
