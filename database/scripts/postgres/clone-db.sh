#!/bin/sh
# Clone an idle seed; CREATE DATABASE refuses to overwrite an existing clone.
set -eu
. "$(dirname "$0")/common.sh"
[ "$#" -ge 2 ] && [ "$#" -le 3 ] || fail "usage: clone-db.sh <seed_db> <target_db> [owner]"
SEED="$1"; TARGET="$2"; OWNER="${3:-$DB_ADMIN}"
seed_database "$SEED"
worktree_database "$TARGET"
identifier "$OWNER"
case "$TARGET" in "${SEED%_seed}_wt_"?*) ;; *) fail "target does not belong to this seed" ;; esac
psql -U "$DB_ADMIN" -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$TARGET\" WITH TEMPLATE \"$SEED\" OWNER \"$OWNER\";"
