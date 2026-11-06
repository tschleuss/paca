#!/bin/sh
# Run as root on the NAS in the prepared migration bundle directory.
# Refuses to overwrite any populated state directory.
set -eu
cd "$(dirname "$0")/.."
umask 077
dc() { docker compose --env-file .env -f docker-compose.yml "$@"; }
# Authenticate over TCP so initialization's temporary socket-only server cannot
# be mistaken for the final PostgreSQL process. Secrets stay inside the container.
pg() { dc exec -T postgres sh -ec 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec "$@"' sh "$@"; }
test -f .env
test -f recovery/database.dump
test -f recovery/state.tar.gz
test -f api-amd64.tar
resume=0
case "${1:-}" in
  '') ;;
  --resume-database) resume=1 ;;
  *) echo 'Usage: restore-orbstack.sh [--resume-database]' >&2; exit 1 ;;
esac
if [ -e .restored-from-orbstack ]; then
  echo 'Restore is already complete. Start the project in Container Manager.' >&2
  exit 1
fi
if [ "$resume" = 0 ] && [ -d state ] && [ -n "$(ls -A state)" ]; then
  echo 'state/ already contains files. Refusing to overwrite an existing deployment.' >&2
  exit 1
fi
sha256sum -c SHA256SUMS
if [ "$resume" = 0 ]; then
docker load -i api-amd64.tar
dc config -q
dc pull postgres valkey rustfs rustfs-init web realtime gateway
mkdir -p state/postgres state/valkey state/rustfs state/plugins/backend state/plugins/frontend state/plugins/mcp state/plugins/skills state/caddy/data state/caddy/config
# Restore storage, streams, plugin files and the TLS CA. Never copy the raw
# ARM PostgreSQL directory; restore its logical dump into a fresh AMD64 database.
dbimage=postgres:16-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea
docker run --rm --network none --user 0:0 --entrypoint sh \
  -v "$PWD/recovery:/recovery:ro" -v "$PWD/state:/state" \
  "$dbimage" -ec 'tar -xzf /recovery/state.tar.gz -C /state ./rustfs ./valkey ./plugins ./caddy'
else
  # Resume after a container-creation failure without extracting over storage.
  for path in state/rustfs state/valkey state/plugins state/caddy state/postgres; do
    test -d "$path" || { echo "Missing restored directory: $path" >&2; exit 1; }
  done
  running=$(dc ps --status running --services)
  for service in $running; do
    [ "$service" = postgres ] || { echo "Stop $service before resuming database restore." >&2; exit 1; }
  done
  dc config -q
fi
dc up -d --wait --wait-timeout 180 postgres
attempt=0
until pg psql -h 127.0.0.1 -U paca -d paca -Atc 'SELECT 1' >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo 'PostgreSQL did not become ready for SQL. Recent logs:' >&2
    dc logs --tail 60 postgres
    exit 1
  fi
  sleep 2
done
tables=$(pg psql -h 127.0.0.1 -U paca -d paca -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
if [ "$tables" != 0 ]; then
  echo 'Database is not empty. Refusing to restore.' >&2
  exit 1
fi
pg pg_restore -h 127.0.0.1 --exit-on-error --single-transaction --no-owner --no-privileges -U paca -d paca < recovery/database.dump
dc stop postgres
touch .restored-from-orbstack
echo 'Restore complete. Create the paca-synology project in Container Manager using this directory and its existing docker-compose.yml, then start it.'
echo 'The first API start applies migrations 79 and 80. Keep the original encrypted backup for rollback.'
