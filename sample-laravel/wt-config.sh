# Trusted project metadata, sourced after the root .env.
PREFIX=sample-laravel
SOURCE_PATH_REL=backend/source
MAIN_DB=sample_laravel
DB_HOST=mysql
DB_USERNAME=root

# Called only after the labelled worktree runtime exists.
wt_post_spin() {
  local slug="$1" container="$2" worktree="$3"
  local src="$worktree/sample-laravel/backend/source"
  if [[ ! -f "$src/.env" ]]; then
    cp "$src/.env.example" "$src/.env"
    python3 - "$src/.env" "$(wt_url)" "$DB_NAME" <<'ENVFILE'
from pathlib import Path
import sys
path, url, database = sys.argv[1:]
p = Path(path)
updates = {"APP_URL": url, "DB_DATABASE": database}
lines = p.read_text().splitlines()
for key, value in updates.items():
    lines = [line for line in lines if not line.startswith(key + "=")]
    lines.append(key + "=" + value)
p.write_text("\n".join(lines) + "\n")
ENVFILE
  fi
  docker exec -w /var/www/html "$container" composer install --no-interaction --prefer-dist
  if grep -q '^APP_KEY=$' "$src/.env"; then
    docker exec -w /var/www/html "$container" php artisan key:generate
  fi
  if [[ -f "$src/package-lock.json" ]]; then
    docker exec -w /var/www/html "$container" npm ci --no-audit --no-fund
  elif [[ -f "$src/package.json" ]]; then
    docker exec -w /var/www/html "$container" npm install --no-audit --no-fund
  fi
  if [[ -f "$src/package.json" ]]; then
    docker exec -w /var/www/html "$container" npm run build
  fi
  # Laravel migrations remain an explicit developer action against this clone.
}
