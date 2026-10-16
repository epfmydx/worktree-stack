#!/bin/sh
# Capture the source successfully before replacing its development seed.
set -eu
. "$(dirname "$0")/common.sh"
[ "$#" -ge 2 ] && [ "$#" -le 3 ] || fail "usage: seed-from.sh <main_db> <seed_db> [owner]"
MAIN="$1"; SEED="$2"; OWNER="${3:-$DB_ADMIN}"
identifier "$MAIN"
seed_database "$SEED"
identifier "$OWNER"
[ "$SEED" = "${MAIN}_seed" ] || fail "seed must be named <main_db>_seed"
dump_temporary
pg_dump -U "$DB_ADMIN" -d "$MAIN" > "$dump_file"
psql -U "$DB_ADMIN" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$SEED' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS "$SEED";
CREATE DATABASE "$SEED" OWNER "$OWNER";
SQL
psql -U "$DB_ADMIN" -d "$SEED" -v ON_ERROR_STOP=1 < "$dump_file"
