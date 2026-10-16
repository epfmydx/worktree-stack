#!/bin/sh
# Strict identifiers keep SQL names and literals unambiguous.
set -eu
fail() { echo "$(basename "$0"): $*" >&2; exit 1; }
identifier() {
  case "$1" in ''|[0-9]*|*[!A-Za-z0-9_]*) fail "invalid SQL identifier: $1" ;; esac
  [ "${#1}" -le 63 ] || fail "SQL identifier is longer than 63 characters"
}
worktree_database() {
  identifier "$1"
  case "$1" in *_wt_?*) ;; *) fail "refusing a non-worktree database: $1" ;; esac
}
seed_database() {
  identifier "$1"
  case "$1" in ?*_seed) ;; *) fail "seed database must end in _seed" ;; esac
}
dump_temporary() {
  umask 077
  dump_file=$(mktemp "${TMPDIR:-/tmp}/worktree-stack-dump.XXXXXX")
  trap 'rm -f "$dump_file"' 0
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM
}
DB_ADMIN="${POSTGRES_USER:-postgres}"
identifier "$DB_ADMIN"
export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
