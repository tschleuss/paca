# Paca on OrbStack, with outbound access blocked

This runs Paca on this Mac at **https://localhost:8443**. The NAS holds encrypted backups; it does not run the application. It uses Docker Compose because Paca needs several services. `Dockerfile` builds the small firewall/backup tools image; the application images retain the previously reviewed digest pins.

```sh
cd /Users/tschleuss/Documents/Repositories/paca/deploy/orbstack
python3 paca.py init            # first setup: build tools, generate secrets/key, verify NAS
python3 paca.py start
python3 paca.py verify-network
python3 paca.py backup
python3 paca.py install-schedule
```

Source files stay in the repository. Running configuration, scripts, credentials, local archives and logs are installed under **`~/Library/Application Support/Paca-OrbStack/`**. This avoids launchd access problems with protected Documents folders and keeps runtime secrets independent of git cleanup. Source commands address that same installed runtime.

The initial setup has already been executed on this Mac. `init` preserves existing credentials and encryption keys; do not delete `secrets/` when updating. `start` works without the NAS mounted after initialization. This is a separate instance from the earlier NAS evaluation files and does not import Trello automatically.

For subsequent examples using relative paths, first enter the installed runtime:

```sh
cd "$HOME/Library/Application Support/Paca-OrbStack"
```

## Open the app and connect agents

The admin username/password are in the ignored, mode-600 `.env` file (`ADMIN_USERNAME` / `ADMIN_PASSWORD`). If prompted, complete the first-login password change; save your chosen password in a password manager. Do not post `.env` in chat or commit it.

Caddy uses a private local certificate authority. Its **public** root is copied to `secrets/root.crt` on `start`. For a browser without certificate warnings, import this public root into Keychain Access and trust it for SSL. No trust-store settings are changed automatically. To verify from the terminal:

```sh
curl --cacert secrets/root.crt https://localhost:8443/api/healthz
```

For workstation MCP clients, follow the existing [agent setup guide](https://github.com/tschleuss/paca/blob/synology-lan/HOW_TO.md#5-connect-agents-from-your-computers), using `PACA_API_URL=https://localhost:8443` and this instance's public root certificate. Generate service-account API keys in this instance. The existing locked client files are in the repository at `deploy/synology/agents/`. Do not append `/api` to the origin.

Only this Mac's loopback port is published. Other LAN computers cannot reach it through the Mac's LAN IP by default. Supporting agents on other LAN machines would require an intentional change to the bind address, hostname/certificate and inbound access policy. No public exposure is configured.

## What “no internet” means here

- A dedicated network keeper installs **IPv4 and IPv6 OUTPUT DROP** rules before any application starts. OrbStack needs a regular bridge for host port publishing; the namespace firewall enforces the outbound policy. An internal-only bridge was tested and did not publish the browser port on this engine.
- PostgreSQL, Valkey, RustFS, API, realtime, web and Caddy all share that guarded network namespace. They communicate through numeric loopback addresses. No external DNS is needed.
- Loopback service traffic and replies to established connections are allowed. All **new non-loopback outbound connections** are blocked, including public IPs, other LAN devices and the Mac/VM gateway. DNS to Docker's embedded resolver is explicitly blocked too.
- New inbound traffic is accepted only on container TCP 443. Database/cache/object-store ports are not exposed, even through direct container-IP access.
- The keeper needs NET_ADMIN only while setting up its own namespace. It then drops all permitted/effective/bounding capabilities. App containers never receive NET_ADMIN or NET_RAW. No Docker socket, host network namespace, SSH agent socket or NAS share is mounted in app containers.
- The transient backup helper has **network_mode: none**. A normal Mac-side Python job copies encrypted archives to the NAS using the existing SMB mount. Application containers cannot use that mount.

Docker/build tooling on the **Mac** still needs internet access to download/build/update images. Running local agents and browsers are also outside this container firewall. Their AI provider requests are not blocked by it. A compromised host, Docker daemon, kernel/container escape, or an operator attaching another network is outside this protection. Containers can return application data to a client that connects to them; this is outbound-connection control, not a data-loss-prevention system.

The custom tools image initially downloads Alpine packages during build. App image pins are unchanged from the previous review, which recorded dependency vulnerabilities. Network isolation reduces opportunities for outbound access; it does not repair application vulnerabilities. See [the earlier review](https://github.com/tschleuss/paca/blob/synology-lan/deploy/synology/REVIEW.md).

### Domain or port allowlists

The default external allowlist is **empty**. This works for the board, documents, uploads and workstation-driven MCP. In-NAS agent runners remain omitted. Marketplace downloads, outbound webhooks/email, cloud SSO, GitHub API calls from Paca and in-app LLM provider calls cannot work with this policy.

Allowing outbound TCP 443 globally would permit contact with arbitrary HTTPS servers. A domain allowlist needs a controlled egress proxy, destination validation, DNS controls and blocking of direct-IP bypasses. None is required for the current offline core, so this deployment avoids that extra service. Add an explicitly reviewed proxy policy later if there is a concrete integration you need; do not remove OUTPUT DROP as a shortcut.

## Backups

The installed user LaunchAgent runs a backup every **six hours while this Mac is awake and you are logged in**, and on filesystem mounts. It never starts a stopped application. It cannot back up while the Mac is asleep or powered off. OrbStack must be running.

The default destination is:

```
/Volumes/Personal/Backups/Paca-OrbStack/<instance-id>/
```

Each instance has its own directory and target marker. The job confirms that `/Volumes/Personal/Backups` sits on an actual SMB/NFS mount, compares the mounted share identity, and checks the marker. It refuses to create a substitute local directory when the NAS is absent.

A backup briefly stops application writers, creates a PostgreSQL custom-format dump, stops PostgreSQL, and snapshots the Docker volumes. It restarts the existing containers without replacing the guarded namespace. The encrypted bundle includes database files/dump, attachment bytes, Valkey data, plugins, Caddy CA/certificates, application `.env`, deployment files and recovery metadata. This is a **full backup**, not an incremental one. Duration/storage grow with the data.

Local migration exports, plans and ID journals under the installed `migrations/` directory are also included in the encrypted configuration bundle. Transient `browser-cookies*` and `*.lock` files are excluded. See the repository's `deploy/synology/migration/HOW_TO.md` for the Stash migration and why no sprint is required.

The bundle is encrypted with **age** before leaving the Mac. The NAS receives `.tar.age` archives and SHA-256 checksums. A copy is written with a partial name, read back and verified, then renamed. If the NAS is unavailable, an encrypted local archive remains queued; the job records that NAS delivery is pending and retries on the next backup or mount. No plaintext archive is copied to the NAS.

**Save `secrets/backup.agekey` somewhere separate from this Mac**, such as your password manager's secure file storage. That is the recovery identity. It is deliberately **not included inside its own encrypted backup**. Without it, NAS backups cannot be decrypted after losing the Mac. The public `backup.recipient` cannot decrypt anything.

The Mac keeps the newest four encrypted archives after successful NAS delivery. During a NAS outage, queued local backups are retained. NAS archives are not automatically deleted; monitor free space and apply a retention policy to this dedicated instance directory when appropriate. Back up the recovery identity separately before deleting local data. The NAS copy does not protect against loss of both the NAS and Mac at the same site; an additional offline/offsite copy remains useful.

Commands:

```sh
python3 paca.py backup             # make a consistent encrypted backup and deliver it
python3 paca.py sync-backups       # deliver queued archives without pausing Paca
python3 paca.py status             # service state plus latest backup attempt
python3 paca.py configure-backup   # revalidate after deliberately changing SMB share identity
```

`backups/last-success.json` records the last completed local/NAS backup. `backup-status.json` records the latest attempt, including a skip or failure. Logs are in `logs/backup.log` and `logs/backup-error.log`. Check these after NAS disconnects and periodically test recovery. There is no email/Slack alert configured.

The scheduler is `~/Library/LaunchAgents/com.tschleuss.paca-orbstack.backup.plist`. To remove just the schedule:

```sh
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.tschleuss.paca-orbstack.backup.plist"
rm "$HOME/Library/LaunchAgents/com.tschleuss.paca-orbstack.backup.plist"
```

## Recovery

Use a separate empty deployment directory/project for a restore drill, or stop the failed instance before disaster recovery. For the drill, use explicit `docker compose -p paca-restore --project-directory RESTORE_DIR --env-file RESTORE_DIR/.env -f RESTORE_DIR/compose.yaml` commands. **Do not run `paca.py start` from a clone expecting a second instance:** that controller always manages the installed main instance in Application Support. Preserve the original archives. Do not extract an archive over running data, and do not use `docker compose down -v` on the working instance.

1. Copy a selected NAS `.tar.age` archive and its checksum into the local ignored `backups/` directory. Compare `shasum -a 256` output with the stored checksum.
2. Ensure the saved recovery identity is available as `secrets/backup.agekey`. Decrypt using the network-disabled helper:

```sh
mkdir -p backups/recovery
# Replace BACKUP with the selected archive filename.
docker --context orbstack compose --env-file .env -f compose.yaml run --rm --no-deps backup \
  age -d -i /keys/backup.agekey -o /work/recovery/bundle.tar /work/BACKUP.tar.age
tar -tf backups/recovery/bundle.tar
```

3. Unpack that bundle into a private recovery working directory. It contains `configuration/`, `database.dump` and `state.tar.gz`. The configuration includes credentials: protect and remove the temporary plaintext files after testing. Never share the decrypted bundle.
4. In an **empty second Compose project** using the saved deployment/configuration, create fresh named volumes with the maintenance helper. Refuse to continue if the target volumes contain existing data. Extract `state.tar.gz` inside that helper at `/snapshot`, preserving numeric ownership. Copying the cold database files requires the same PostgreSQL major version and compatible architecture.
5. Start the restored project with a different `-p` project name and unused `PACA_PORT`/`PUBLIC_URL`. Its firewall keeper and every app service must be recreated together. Check login, task counts, sample documents and attachment downloads.
6. For a different CPU architecture or PostgreSQL migration, initialize a genuinely empty database and use `pg_restore -U paca -d paca --no-owner --exit-on-error < database.dump`, with API stopped. Retain the matching attachment/plugin/Caddy state and `.env`. A DB dump alone does not contain attachments.

See [VALIDATION.md](VALIDATION.md) for the local restore drill performed on this implementation.

## Stop and update

```sh
python3 paca.py stop   # removes containers/networks; keeps named volumes and backups
python3 paca.py start
```

Automatic Docker restart policies are disabled: daemon restart policies do not honor Compose health dependencies and could otherwise race firewall initialization. After restarting OrbStack/the Mac, run `python3 paca.py start`; it waits for the firewall before starting apps. A crashed service needs an explicit controlled restart.

All app containers depend on the firewall keeper. When updating/rebuilding the keeper, stop the **whole** stack and recreate it; do not independently replace the keeper while leaving app containers in an older network namespace. Updating only the keeper does not move existing processes to a new namespace. `verify-network` catches mismatched namespaces.

Before an update, create/verify a backup, review upstream changes and migration requirements, then update explicit image digests and the matching workstation MCP client. Do not use `latest`, Watchtower or the upstream installer on this customized directory. Do not run an old API image against a newly migrated database to roll back: restore the complete pre-update backup instead.

To install source updates, stop the stack, run `python3 paca.py init` from the repository source directory to refresh installed code/configuration and rebuild tools, then start and verify it. `init` preserves private runtime state.

Only `deploy/orbstack` source files are committed. Credentials, encryption identities, plaintext staging data, archives, status and logs are ignored by Git and excluded from Docker build context.
