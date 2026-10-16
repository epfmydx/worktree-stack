#!/bin/sh
# Terminate sessions and drop only an explicitly named worktree DB.
set -eu
. "$(dirname "$0")/common.sh"
[ "$#" -eq 1 ] || fail "usage: drop-db.sh <target_db>"
TARGET="$1"
worktree_database "$TARGET"
psql -U "$DB_ADMIN" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$TARGET' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS "$TARGET";
SQL
