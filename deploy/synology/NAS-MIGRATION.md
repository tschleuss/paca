# OrbStack to Synology migration (Paca v0.20.2)

The prepared private bundle retains the existing database (users, roles, API keys,
boards, tasks, documents and application settings), object storage, plugin files,
Valkey state, and encryption/authentication secrets. It uses the fork's API image
to preserve the folder-scoped document permission fix. Web and realtime are
upstream v0.20.2 images. Existing infrastructure versions are retained to avoid
combining this move with database or object-storage upgrades.

The Mac source instance is still running v0.20.0+local.1. The repository's OrbStack
configuration is prepared for v0.20.2 but has not been applied to that instance.
The NAS starts from the backup taken 2026-11-06 at 22:15 UTC; any later Mac writes
are outside this snapshot. Stop agents from writing to the Mac during cutover.

## Copy the private bundle

The bundle is generated outside Git at:

`~/Library/Application Support/Paca-OrbStack/nas-migration-0.20.2/`

Copy the contents to File Station's `docker/paca` folder, which is
`/volume2/docker/paca` on this NAS. Include the hidden `.env` file. Do not use the
old evaluation `.env` from the repository. This bundle contains decrypted data
and secrets; keep access restricted to your NAS administrator account.

Confirm `.env` contains your intended network settings:

```dotenv
NAS_BIND_IP=192.168.0.146
PACA_HOST=192.168.0.146
PACA_PORT=8443
LAN_CIDR=192.168.0.0/24
PUBLIC_URL=https://192.168.0.146:8443
```

The LAN allowlist assumes clients are on 192.168.0.x. Change LAN_CIDR if your
trusted client network differs. All original secrets are already copied from the
backup; do not regenerate them or run init.sh for this migration.

## Restore once on the NAS

In DSM Control Panel > Terminal & SNMP, enable SSH temporarily. From your Mac,
connect with your NAS administrator username, then run:

```sh
ssh YOUR_NAS_USERNAME@192.168.0.146
cd /volume2/docker/paca
sudo sh scripts/restore-orbstack.sh
```

The script checks bundle hashes, imports the AMD64 API image, pulls the other
images, creates missing bind folders, restores file ownership and storage, and
loads the PostgreSQL dump into an empty database. It stops PostgreSQL afterward.
It refuses to overwrite populated state. If it fails, keep its output and diagnose
the error; do not delete state or repeatedly initialize the project.

## Start and manage through Container Manager

Create a project named **paca-synology**, path **/docker/paca**, source **Use
existing docker-compose.yml**. Leave Web Station off. Start the project.
The services use the same Compose project name as the restore script.

Open **https://192.168.0.146:8443**. Caddy uses the restored private CA; the URL
uses HTTPS with an internally issued certificate. If the Mac already trusts the
old Paca root certificate, it should trust the newly issued IP certificate too.
For another computer, import only the public CA certificate; never its private key.
Login with your existing Paca account/password. No new owner account is required.
The API automatically upgrades the database with migrations 79 and 80.

Confirm existing projects, task/document content and an attachment download.
Change agents' Paca origin from localhost to https://192.168.0.146:8443 and retain
their API keys. Caddy health/route: `/api/healthz`. Keep the Mac and encrypted
backup available until the NAS copy works. Avoid writes to both copies.

If needed, stop the NAS project and reconnect agents to the unchanged Mac.
NAS changes made after cutover will not appear on the Mac automatically.

## Scope

The NAS stack's backend network blocks new outbound connections; workstation
agents remain external. The runner/Docker socket is omitted. Existing scan/review
documents describe the older v0.19.1 baseline; they are historical evidence, not
a fresh v0.20.2 security assessment. The NAS has 32 GB RAM.

Keep the encrypted original archive and recovery key. Once the migration is
confirmed, remove the decrypted recovery staging files from both machines using
your normal file management, and configure scheduled NAS backups separately.
The Mac's existing schedule backs up only the Mac instance.

## Resume after the NanoCPUs error

This DSM kernel does not support CPU CFS quotas. The Synology Compose therefore
omits `cpus` limits; memory limits remain. If the first restore stopped at
`NanoCPUs can not be set`, file extraction has already run but PostgreSQL has not
started. With the updated bundle files, resume only the database phase:

```sh
cd /volume2/docker/paca
sudo sh scripts/restore-orbstack.sh --resume-database
```

This checks for an empty database and refuses to overwrite an existing restore.
It leaves the restored object storage and other files in place.

The first PostgreSQL initialization uses a temporary Unix-socket-only server.
The current health check and restore script use TCP and wait for an actual SQL
query, preventing a premature readiness signal while that temporary server stops.
The NAS kernel also lacks PID-count cgroups; that optional limit is omitted.
