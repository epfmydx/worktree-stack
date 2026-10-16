#!/bin/sh
# Drop only an explicitly named worktree database.
set -eu
. "$(dirname "$0")/common.sh"
[ "$#" -eq 1 ] || fail "usage: drop-db.sh <target_db>"
TARGET="$1"
worktree_database "$TARGET"
mysql -uroot -e "DROP DATABASE IF EXISTS \`$TARGET\`;"
