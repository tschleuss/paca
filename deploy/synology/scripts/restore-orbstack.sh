#!/bin/sh
# Run as root on the NAS in the prepared migration bundle directory.
# Refuses to overwrite any populated state directory.
set -eu
cd "$(dirname "$0")/.."
umask 077
dc() { docker compose --env-file .env -f docker-compose.yml "$@"; }
test -f .env
test -f recovery/database.dump
test -f recovery/state.tar.gz
test -f api-amd64.tar
if [ -d state ] && [ -n "$(ls -A state)" ]; then
  echo 'state/ already contains files. Refusing to overwrite an existing deployment.' >&2
  exit 1
fi
sha256sum -c SHA256SUMS
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
dc up -d --wait --wait-timeout 180 postgres
tables=$(dc exec -T postgres psql -U paca -d paca -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
if [ "$tables" != 0 ]; then
  echo 'Database is not empty. Refusing to restore.' >&2
  exit 1
fi
dc exec -T postgres pg_restore --exit-on-error --no-owner --no-privileges -U paca -d paca < recovery/database.dump
dc stop postgres
touch .restored-from-orbstack
echo 'Restore complete. Create the paca-synology project in Container Manager using this directory and its existing docker-compose.yml, then start it.'
echo 'The first API start applies migrations 79 and 80. Keep the original encrypted backup for rollback.'
