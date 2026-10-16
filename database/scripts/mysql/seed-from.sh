#!/bin/sh
# Capture the source successfully before replacing its development seed.
set -eu
. "$(dirname "$0")/common.sh"
[ "$#" -ge 2 ] && [ "$#" -le 3 ] || fail "usage: seed-from.sh <main_db> <seed_db> [owner]"
MAIN="$1"; SEED="$2"
identifier "$MAIN"
seed_database "$SEED"
[ "$SEED" = "${MAIN}_seed" ] || fail "seed must be named <main_db>_seed"
dump_temporary
mysqldump -uroot --single-transaction --routines --triggers "$MAIN" > "$dump_file"
mysql -uroot -e "DROP DATABASE IF EXISTS \`$SEED\`; CREATE DATABASE \`$SEED\`;"
mysql -uroot "$SEED" < "$dump_file"
