#!/bin/sh
# Dump completely before creating the new clone; never overwrite an existing DB.
set -eu
. "$(dirname "$0")/common.sh"
[ "$#" -ge 2 ] && [ "$#" -le 3 ] || fail "usage: clone-db.sh <seed_db> <target_db> [owner]"
SEED="$1"; TARGET="$2"
seed_database "$SEED"
worktree_database "$TARGET"
case "$TARGET" in "${SEED%_seed}_wt_"?*) ;; *) fail "target does not belong to this seed" ;; esac
dump_temporary
mysqldump -uroot --single-transaction --routines --triggers "$SEED" > "$dump_file"
mysql -uroot -e "CREATE DATABASE \`$TARGET\`;"
mysql -uroot "$TARGET" < "$dump_file"
