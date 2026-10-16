#!/usr/bin/env bash
set -euo pipefail
OUT="$(cd "$(dirname "$0")/.." && pwd)/certs"
mkdir -p "$OUT"
[[ ! -f "$OUT/server.crt" || ! -f "$OUT/server.key" ]] || exit 0
umask 077
openssl req -new -x509 -days 365 -nodes -out "$OUT/server.crt" -keyout "$OUT/server.key" -subj /CN=postgres >/dev/null 2>&1
chmod 644 "$OUT/server.crt"
echo 'Generated local PostgreSQL certificate.'
