# Trusted project metadata, sourced after the root .env.
PREFIX=sample-fastapi
SOURCE_PATH_REL=source
MAIN_DB=sample_fastapi
DB_HOST=postgres
DB_USERNAME="${POSTGRES_USER}"

# Compose installs dependencies and runs Alembic migrations against the clone.
# Override its command in docker-compose.worktree.yml to opt out of migrations.
