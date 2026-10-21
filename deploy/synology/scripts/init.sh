#!/bin/sh
# Run on the Mac or NAS; never overwrite an existing configuration.
set -eu
cd "$(dirname "$0")/.."
umask 077
if [ -e .env ]; then
  echo '.env already exists; leaving it unchanged.' >&2
  exit 1
fi
command -v openssl >/dev/null
cp .env.example .env
for key in POSTGRES_PASSWORD ADMIN_PASSWORD JWT_SECRET ENCRYPTION_KEY INTERNAL_API_KEY STORAGE_ACCESS_KEY_ID STORAGE_SECRET_ACCESS_KEY; do
  value=$(openssl rand -hex 32)
  # Hex-only output is safe for sed and database connection URLs.
  sed "s/^${key}=GENERATE$/${key}=${value}/" .env > .env.tmp
  mv .env.tmp .env
done
chmod 600 .env
mkdir -p state/postgres state/valkey state/rustfs state/plugins/backend state/plugins/frontend state/plugins/mcp state/plugins/skills state/caddy/data state/caddy/config backups migration/private
echo 'Generated .env and state directories. Edit LAN settings in .env before starting.'
