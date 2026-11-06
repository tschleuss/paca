# Synology Paca v0.20.2 deployment

For this Mac-to-NAS move, follow [NAS-MIGRATION.md](NAS-MIGRATION.md). A private
bundle includes the data, existing secrets, restore script and locally built AMD64
API image. The NAS is a DS1821+ with 32 GB RAM at 192.168.0.146.

The fork includes the folder-scoped document-create fix. Web/realtime are pinned
upstream v0.20.2 images. Infrastructure pins are retained. Only the HTTPS gateway
is published; agents execute on workstations and the NAS Docker socket is omitted.

For a fresh empty installation only, run `sh scripts/init.sh`, set network values
in `.env`, and build/import the fork API image listed in `images.lock.json`.
For a migration, preserve the source secrets using the prepared bundle instead.

[REVIEW.md](REVIEW.md), [VALIDATION.md](VALIDATION.md) and security-scan.json record
the historical v0.19.1 evaluation. They have not been repeated for v0.20.2 and
should not be interpreted as current deployment verification. Source/Compose checks
and successful AMD64/ARM64 API builds are recorded for the current update.
