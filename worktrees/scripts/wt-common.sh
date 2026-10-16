#!/usr/bin/env bash
# Shared trusted-config and ownership checks; Bash 3.2 compatible.
WT_LABEL=io.github.epfmydx.worktree-stack
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
wt_fail() { echo "${WT_COMMAND:-worktree-stack}: $*" >&2; exit 1; }
wt_name() { [[ "$1" =~ ^[a-z][a-z0-9-]*$ ]] || wt_fail "$2 must match [a-z][a-z0-9-]*"; }
wt_identifier() {
  [[ "$1" =~ ^[A-Za-z_][A-Za-z0-9_]*$ && ${#1} -le 63 ]] || wt_fail "$2 must be a SQL identifier of at most 63 characters";
}
wt_load_stack() {
  [[ -f "$REPO/.env" ]] || wt_fail "missing $REPO/.env; copy .env.example and configure it first"
  # .env and wt-config.sh are trusted local shell configuration.
  set -a
  . "$REPO/.env"
  set +a
  [[ -n "${STACK_NAME:-}" ]] || wt_fail "STACK_NAME is required in .env"
  wt_name "$STACK_NAME" STACK_NAME
  [[ -n "${DEV_DOMAIN:-}" ]] || wt_fail "DEV_DOMAIN is required in .env"
  [[ "$DEV_DOMAIN" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*$ ]] || wt_fail "invalid DEV_DOMAIN"
  : "${GATEWAY_HTTPS_PORT:=8443}"
}
wt_load_project() {
  PROJECT="$1"
  wt_name "$PROJECT" project
  wt_load_stack
  PROJECT_DIR="$REPO/$PROJECT"
  WT_CONFIG="$PROJECT_DIR/wt-config.sh"
  [[ -f "$WT_CONFIG" ]] || wt_fail "missing $WT_CONFIG"
  PREFIX= MAIN_DB= DB_HOST= DB_USERNAME= SOURCE_PATH_REL=
  unset -f wt_post_spin 2>/dev/null || :
  . "$WT_CONFIG"
  [[ -n "$PREFIX" ]] || wt_fail "PREFIX is required in $WT_CONFIG"
  wt_name "$PREFIX" PREFIX
  if [[ -n "$MAIN_DB" ]]; then
    wt_identifier "$MAIN_DB" MAIN_DB
    [[ "$DB_HOST" == mysql || "$DB_HOST" == postgres ]] || wt_fail "DB_HOST must be mysql or postgres"
    [[ -n "$DB_USERNAME" ]] || wt_fail "DB_USERNAME is required when MAIN_DB is set"
    wt_identifier "$DB_USERNAME" DB_USERNAME
    SEED_DB="${MAIN_DB}_seed"
    wt_identifier "$SEED_DB" SEED_DB
  fi
}
wt_set_worktree() {
  SLUG="$1"
  wt_name "$SLUG" slug
  SLUG_UNDER="${SLUG//-/_}"
  WORKTREE_PATH="$REPO/worktrees/$SLUG"
  OVERRIDE="$PROJECT_DIR/docker-compose.worktree.yml"
  [[ -f "$PROJECT_DIR/docker-compose.yml" && -f "$OVERRIDE" ]] || wt_fail "project needs Compose and worktree override files"
  WT_HOST="${PREFIX}-${SLUG}"
  CONTAINER="${STACK_NAME}-${WT_HOST}"
  DB_NAME=""
  if [[ -n "$MAIN_DB" ]]; then
    DB_NAME="${MAIN_DB}_wt_${SLUG_UNDER}"
    wt_identifier "$DB_NAME" DB_NAME
  fi
  export PROJECT SLUG SLUG_UNDER WORKTREE_PATH PREFIX WT_HOST CONTAINER DB_NAME DEV_DOMAIN STACK_NAME GATEWAY_HTTPS_PORT
}
wt_verify_worktree() {
  [[ -d "$WORKTREE_PATH" ]] || wt_fail "missing worktree $WORKTREE_PATH; create it with git worktree add first"
  python3 - "$REPO" "$WORKTREE_PATH" <<'VERIFY'
import subprocess
import sys
from pathlib import Path
root, worktree = (Path(p).resolve() for p in sys.argv[1:])
def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], stderr=subprocess.PIPE).decode().rstrip("\n")
try:
    if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ValueError("stack directory is not its Git root")
    if Path(git(worktree, "rev-parse", "--show-toplevel")).resolve() != worktree:
        raise ValueError("selected directory is not a Git worktree root")
    common = lambda p: Path(git(p, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
    if common(root) != common(worktree):
        raise ValueError("worktree belongs to another repository")
    registered = git(root, "worktree", "list", "--porcelain", "-z").split("\0")
    if str(worktree) not in {str(Path(v[9:]).resolve()) for v in registered if v.startswith("worktree ")}:
        raise ValueError("worktree is not registered with this stack")
except (ValueError, OSError, subprocess.CalledProcessError) as error:
    print("worktree-stack: " + str(error), file=sys.stderr)
    sys.exit(1)
VERIFY
}
wt_compose() {
  docker compose --env-file "$REPO/.env" -f "$PROJECT_DIR/docker-compose.yml" -f "$OVERRIDE" -p "$CONTAINER" "$@"
}
wt_runtime_ids() {
  docker container ls --all --filter "label=com.docker.compose.project=$CONTAINER" --format '{{.ID}}'
}
wt_check_runtime_ownership() {
  local id actual
  RUNTIME_IDS="$(wt_runtime_ids)" || wt_fail "cannot inventory worktree containers"
  while IFS= read -r id; do
    [[ -n "$id" ]] || continue
    actual="$(docker inspect --format "{{index .Config.Labels \"$WT_LABEL.managed\"}}|{{index .Config.Labels \"$WT_LABEL.stack\"}}|{{index .Config.Labels \"$WT_LABEL.project\"}}|{{index .Config.Labels \"$WT_LABEL.slug\"}}|{{index .Config.Labels \"com.docker.compose.project\"}}|{{index .Config.Labels \"$WT_LABEL.ci\"}}" "$id")" || wt_fail "cannot inspect container $id"
    [[ "$actual" == "true|$STACK_NAME|$PROJECT|$SLUG|$CONTAINER|" || "$actual" == "true|$STACK_NAME|$PROJECT|$SLUG|$CONTAINER|<no value>" || "$actual" == "true|$STACK_NAME|$PROJECT|$SLUG|$CONTAINER|false" ]] || wt_fail "refusing container $id: ownership labels do not match this worktree"
  done <<< "$RUNTIME_IDS"
}
wt_database_container() {
  local ids id actual count=0
  ids="$(docker container ls --filter "label=com.docker.compose.project=${STACK_NAME}-database" --filter "label=com.docker.compose.service=$DB_HOST" --format '{{.ID}}')" || wt_fail "cannot inventory database containers"
  DB_CONTAINER=""
  while IFS= read -r id; do
    [[ -n "$id" ]] || continue
    count=$((count + 1)); DB_CONTAINER="$id"
  done <<< "$ids"
  [[ "$count" -eq 1 ]] || wt_fail "expected one running $DB_HOST in Compose project ${STACK_NAME}-database; found $count"
  actual="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{.State.Running}}' "$DB_CONTAINER")" || wt_fail "cannot inspect database container"
  [[ "$actual" == "${STACK_NAME}-database|$DB_HOST|true" ]] || wt_fail "database container ownership or running state changed"
}
wt_url() {
  local port=""
  [[ "$GATEWAY_HTTPS_PORT" == 443 ]] || port=":$GATEWAY_HTTPS_PORT"
  echo "https://${WT_HOST}.${DEV_DOMAIN}${port}"
}
