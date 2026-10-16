#!/usr/bin/env bash
# Shared command interface. .env is trusted local shell configuration.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[[ -f "$ROOT/.env" ]] || { echo "Missing .env. Run make init." >&2; exit 1; }
set -a
. "$ROOT/.env"
set +a
: "${STACK_NAME:?}" "${DEV_DOMAIN:?}" "${HOST_CONTAINERS_PATH:?}"
[[ "$STACK_NAME" =~ ^[a-z][a-z0-9-]*$ ]] || { echo 'Invalid STACK_NAME' >&2; exit 1; }
[[ "$DEV_DOMAIN" =~ ^[a-z0-9][a-z0-9.-]*\.[a-z]+$ ]] || { echo 'Invalid DEV_DOMAIN' >&2; exit 1; }
for port in GATEWAY_HTTP_PORT GATEWAY_HTTPS_PORT VITE_PORT MYSQL_PORT POSTGRES_PORT REDIS_PORT; do
  value="${!port}"
  [[ "$value" =~ ^[0-9]+$ ]] && ((10#$value >= 1 && 10#$value <= 65535)) || { echo "Invalid $port" >&2; exit 1; }
done
compose() { local project="$1"; shift; docker compose --env-file "$ROOT/.env" -f "$ROOT/$project/docker-compose.yml" "$@"; }
network() {
  local name="$1" subnet="${2:-}" owner
  if docker network inspect "$name" >/dev/null 2>&1; then
    owner="$(docker network inspect -f '{{index .Labels "io.github.epfmydx.worktree-stack.stack"}}' "$name")"
    [[ "$owner" = "$STACK_NAME" ]] || { echo "Network $name exists without this stack's ownership label; choose another STACK_NAME." >&2; exit 1; }
  else
    local args=(network create --label "io.github.epfmydx.worktree-stack.stack=$STACK_NAME")
    [[ -z "$subnet" ]] || args+=(--subnet "$subnet")
    docker "${args[@]}" "$name" >/dev/null
  fi
}
networks() { network "$STACK_NAME-dev" "$DEV_SUBNET"; network "$STACK_NAME-db"; }
certs() { "$ROOT/gateway/scripts/gen-certs.sh" "${1:-}"; "$ROOT/database/postgres17/scripts/gen-postgres-certs.sh"; }
case "${1:-}" in
  networks) networks ;;
  certs-init) certs ;;
  certs-regen) certs --force ;;
  base) docker build --build-arg "PHP_VERSION=$PHP_VERSION" -t "$STACK_NAME/php-laravel:$PHP_VERSION" "$ROOT/base-images/php-laravel" ;;
  infra)
    networks
    certs
    for project in dnsmasq gateway database redis; do compose "$project" up -d --wait; done ;;
  infra-down)
    for project in dashboard redis database gateway dnsmasq; do compose "$project" down; done ;;
  dashboard) networks; compose dashboard up -d --build --wait ;;
  dashboard-down) compose dashboard down ;;
  config)
    for project in dnsmasq gateway database redis dashboard sample-laravel sample-fastapi; do compose "$project" config --quiet; done
    echo 'All main Compose configurations are valid.' ;;
  ps)
    for project in dnsmasq gateway database redis dashboard sample-laravel sample-fastapi; do compose "$project" ps; done ;;
  up|down|build|restart|logs|shell|sample-setup)
    action="$1"; project="${2:-}"
    [[ "$project" =~ ^[a-z][a-z0-9-]*$ && -f "$ROOT/$project/docker-compose.yml" ]] || { echo 'Pass p=<project> with an existing Compose file.' >&2; exit 1; }
    case "$action" in
      up) compose "$project" up -d --wait ;;
      down) compose "$project" down ;;
      build) compose "$project" build ;;
      restart) compose "$project" restart ;;
      logs) compose "$project" logs -f ;;
      shell) compose "$project" exec backend sh ;;
      sample-setup)
        case "$project" in
          sample-laravel)
            compose database exec -T mysql sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "CREATE DATABASE IF NOT EXISTS sample_laravel CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"'
            compose "$project" up -d --build --wait
            compose "$project" exec -T backend sh -ec 'composer install --no-interaction --prefer-dist; test -f .env || cp .env.example .env; if ! grep -q "^APP_KEY=base64:" .env; then php artisan key:generate; fi; php artisan migrate --force'
            ;;
          sample-fastapi)
            exists="$(compose database exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_database WHERE datname = 'sample_fastapi'")"
            [[ "$exists" = 1 ]] || compose database exec -T postgres createdb -U "$POSTGRES_USER" sample_fastapi
            compose "$project" up -d --build --wait
            ;;
          *) echo 'sample-setup supports sample-laravel and sample-fastapi only.' >&2; exit 1 ;;
        esac
        echo "URL: https://$project.$DEV_DOMAIN:$GATEWAY_HTTPS_PORT (configure DNS/host entry and trust your local certificate)."
        ;;
    esac ;;
  *) echo 'Unknown action; see make help.' >&2; exit 1 ;;
esac
