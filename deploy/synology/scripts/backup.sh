#!/bin/sh
# Consistent cold backup: maintenance downtime, all state + config + logical DB.
# Run as NAS root from DSM Task Scheduler. Never run concurrently with updates.
set -eu
cd "$(dirname "$0")/.."
umask 077
dc() { docker compose --env-file .env -f compose.yaml "$@"; }
if ! mkdir .backup-lock 2>/dev/null; then
  echo 'Backup lock exists. Check for an active backup before removing .backup-lock.' >&2
  exit 1
fi
work=
resume=0
cleanup() {
  rc=$?
  trap - EXIT HUP INT TERM
  if [ "$resume" = 1 ]; then
    if ! dc up -d; then rc=1; fi
  fi
  if [ -n "$work" ]; then rm -rf "$work"; fi
  rmdir .backup-lock
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
dc config -q
mkdir -p backups
work=$(mktemp -d ./backups/.working.XXXXXX)
resume=1
dc stop gateway api realtime web rustfs valkey
dc exec -T postgres pg_dump -U paca -d paca -Fc > "$work/database.dump"
test -s "$work/database.dump"
dc exec -T postgres pg_restore --list < "$work/database.dump" > /dev/null
dc stop postgres
cp .env compose.yaml Caddyfile images.lock.json "$work/"
cp -R scripts "$work/"
dc config > "$work/compose.resolved.yaml"
tar -czf "$work/state.tar.gz" state
tar -tzf "$work/state.tar.gz" > /dev/null
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="backups/paca-${stamp}.tar"
tar -cf "$out.partial" -C "$work" .
mv "$out.partial" "$out"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$out" > "$out.sha256"
else
  shasum -a 256 "$out" > "$out.sha256"
fi
echo "Backup complete: $out (contains secrets; encrypt off-device copies)."
# Retention is intentionally manual: never erase the only known-good recovery point.
