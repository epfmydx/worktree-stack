#!/usr/bin/env bash
# Local-only per-install CA and certificate; no changes to the host trust store.
set -euo pipefail
: "${DEV_DOMAIN:?DEV_DOMAIN required}"
OUT="$(cd "$(dirname "$0")/.." && pwd)/certs"
mkdir -p "$OUT"
umask 077
if [[ -f "$OUT/fullchain.pem" && -f "$OUT/privkey.pem" && "${1:-}" != --force ]]; then
  echo 'Keeping existing gateway certificates (use make certs-regen after changing DEV_DOMAIN).'
  exit 0
fi
cd "$OUT"
if [[ ! -f dev-ca.key || ! -f dev-ca.pem ]]; then
  openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 3650 -keyout dev-ca.key -out dev-ca.pem -subj "/CN=Worktree Stack local development CA" >/dev/null 2>&1
fi
openssl req -new -newkey rsa:2048 -nodes -keyout privkey.pem -out server.csr -subj "/CN=*.${DEV_DOMAIN}" >/dev/null 2>&1
trap 'rm -f server.csr server.ext' EXIT
cat > server.ext <<EOF
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:${DEV_DOMAIN},DNS:*.${DEV_DOMAIN}
EOF
openssl x509 -req -in server.csr -CA dev-ca.pem -CAkey dev-ca.key -CAcreateserial -out fullchain.pem -days 365 -sha256 -extfile server.ext >/dev/null 2>&1
chmod 644 dev-ca.pem fullchain.pem
echo 'Generated local gateway certificate. Trust dev-ca.pem only on your own development devices.'
