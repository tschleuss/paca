# OrbStack v0.20.0 upgrade validation — 2026-11-04

Upstream release tag `v0.20.0` was merged into the customized fork, preserving
published history and local backup/egress/gateway/Valkey fixes. All three running
application images report version 0.20.0 and source revision
`ba38b7523fe212a4d24d2bb62b9628db4299ee08`. Registry index digests are pinned in
`images.lock.json`; infrastructure image pins remain unchanged.

Before migration, `paca-20261104T132909Z.tar.age` was encrypted and verified on
the NAS. Its SHA-256 is
`ab4acab82373159327df4c3d37f4ba4e84a9a9d9805d8c5d62c9b94a8fcda323`.
Local checksum verification was repeated before deployment. The whole stack was
stopped, `paca.py init` installed the updated source, and startup health ordering
was honored. Runtime upgrade metrics/screenshots are kept privately under
`diagnostics/upgrade-v0.20.0-20261104/`.

Passed:

- Migrations 73–78 applied. Before disposable test fixtures, row counts and
  sorted-ID fingerprints match for 5 projects, 980 task records, 26 documents,
  1 file and 2 users. New MFA enforcement is off and the IP allow-list is empty.
- Valkey password authentication works and unauthenticated PING is refused.
  The 512 MB `noeviction` limit and 1 GB container limit remain in place;
  authenticated temporary-key write/read succeeds. No stream cleanup was applied.
- Nine controller tests cover the six existing backup safeguards plus atomic,
  idempotent addition of a new secret, preservation of existing credentials, and
  retaining the original file on failed replacement. Config validates without
  exposing secrets. Existing agent keys and the private TLS authority are retained.
- Outbound IPv4/IPv6 and DNS isolation checks pass. All application services
  share the guarded network namespace; the keeper retains no capabilities.
- All four Stash profiles authenticate. Their real MCP probes pass curated tool
  discovery, project/task/schema/member/document reads, project restrictions,
  worker status/comment write/read-back and reviewer write refusals. Fourteen
  direct API handoff checks pass, including worker write confinement and reviewer
  read-only access. Disposable tasks/docs/folder were removed through the API.
- The authenticated Stash Timeline renders in a headless browser with no reported
  page errors. The private CA was verified independently; the disposable browser
  trusted only the exact leaf public-key pin. Temporary cookie files and the
  browser session were removed after verification; host trust settings were not
  modified.
- API startup is healthy. Release discovery warnings are expected because the
  existing firewall blocks GitHub access; no API ERROR or Valkey OOM was observed.

The first task-probe fixture used an incorrect status ID and failed safely on its
disposable task. The corrected probe reads live status IDs and all four profiles
pass; no production task was modified. Existing pinned clients were retained:
npm refused 0.20.0 under this machine's release-age restriction, so the release-age
rule was not bypassed. Stash's working adapter remains `0.19.1-2` and the generic
client remains 0.19.2. The full upstream test suite, a fresh image vulnerability
audit and a disaster-recovery drill were not repeated. MFA enrollment, passkey
enrollment and external Git/LLM integrations were not enabled by this deployment.

The event-stream retention limitation remains. Rollback after migration requires
restoring the complete pre-upgrade archive with its old configuration/images,
not starting the old API image against the migrated database.

# OrbStack incident validation — 2026-11-04

The health endpoint returned 200 while Valkey was above its 128 MB `noeviction`
limit. Full-sample memory inspection attributed approximately 66.4 MB each to
`paca.activities` and `paca.plugin_events`; all consumer groups reported zero
pending/unread entries. API logs contained thousands of scheduler OOM warnings,
cache-set failures and browser auth-refresh 500 responses. PING alone missed this
write failure.

The application limit is now 512 MB, with a 1 GB container limit. Runtime Compose
was backed up privately, updated from source and validated. Valkey was recreated
under the existing lifecycle lock with the same persistent volume and guarded
namespace, leaving all event entries and the no-eviction policy intact. Inspection
confirms the persisted container command and resource limit. A temporary key with
a 30-second TTL was successfully written/read; scheduler locks resumed and no new
OOM warnings appeared after the change. Network isolation and six backup safeguard
tests passed. Consumers briefly logged `LOADING` while the existing dataset was
read during recreation, then recovered. The scheduled encrypted local/NAS backup completed at 12:17 UTC
before this adjustment; no restore drill was repeated.

Stash access checks independently passed for all four worker/reviewer profiles:
direct project/task HTTP reads and real MCP project/task/handoff reads. Both
Claude and Codex board-script epic listings passed. Active key issuance remains
2026-10-22 with expiry in January 2027; no keys were rotated. Installed adapter
and policy files match Stash's committed `0.19.1-2` release.

The reported Claude editor session rejection was separately reproduced: it omitted
the required `projectId`, supplied `number` instead of numeric `taskNumber`, and
used the board helper's epic-only `show` command on child task STAS-976. These
validation failures are masked by a generic adapter error. The same Claude worker
launcher successfully read STAS-976 with the published argument schema. No Stash
task/document writes or credential changes were performed by these diagnostics.

Retained event streams remain unbounded upstream. This capacity adjustment restores
headroom; it does not establish a long-term retention policy or repair historical
events that may have failed to publish while Valkey rejected writes.

# OrbStack update validation — 2026-10-27

The customized `synology-lan` branch merged upstream `master` at
`8e74bcdc3703ca6e4463af35e63cfd0af840d371` (77 upstream commits), preserving
published fork history. Local backup branches retain the previous `master` and
`synology-lan` tips. The merged upstream tree did not change either custom
deployment directory.

OrbStack runs the latest published release **v0.19.2**, source revision
`e120af34420c93eab249add14846f2a4eba18f8b`. All three application image labels
match this revision; exact registry index digests are in `images.lock.json`.
Infrastructure image pins, loopback exposure, outbound firewall and gateway
`init: true` remain in place. Later unreleased source changes are available in
the fork but are not deployed to this database. The Synology evaluation remains
on its original application pins.

Verified on the running instance:

- Before the upgrade, `paca-20261027T213320Z.tar.age` was encrypted, copied to
  the NAS, read back and checksum-verified. SHA-256:
  `2f4c52ceb201eff2c4e3f0de883fc3e8cbc09c0511f147e5a709f6bfb3c482a1`.
- The whole stack was stopped, installed source refreshed with `paca.py init`,
  then started with health ordering. Existing private runtime state was retained.
- Database migrations 71 and 72 applied. Counts before and after match:
  5 projects, 705 tasks, 12 documents and 1 attachment/file record.
- Trusted HTTPS health and HTML return 200; every script/stylesheet referenced
  by the HTML loads. The Socket.IO polling endpoint returns its opening handshake.
- `paca.py verify-network` passes: local API access works, external IPv4/IPv6
  and both public/embedded DNS are blocked, all services share the guarded
  namespace, and the keeper retains no capabilities.
- Six backup safeguard tests pass. The disposable gateway regression reproduces
  the failure in both controls, while the configured offline gateway completes
  300 HTTPS probes with zero zombies.
- Merged source validation passes: 41 realtime tests and 731 MCP tests; the MCP
  TypeScript build also succeeds. These do not constitute the full upstream suite.
- The locked workstation MCP package is updated to 0.19.2, retaining SDK 1.32.1
  and uuid overrides. Its transitive body-parser is patched to 2.4.0;
  `npm audit --omit=dev` reports zero vulnerabilities. No separate installed
  runtime was present at `~/.local/share/paca-mcp` to update.

The application images were not subjected to a new full vulnerability audit.
No restore drill or authenticated browser workflow was repeated for this update;
the previous restore evidence below remains historical. Rollback after migrations
requires restoring the complete pre-upgrade backup, not starting v0.19.1 against
the migrated database. The image lock is now installed and included in subsequent
encrypted backups.

# Initial OrbStack validation — 2026-10-22

Tested on this Mac's ARM64 OrbStack Docker Engine 29.8.2 / Compose 5.5.0. App images use the prior reviewed digest pins; this work does not assert that their previously reported dependency vulnerabilities are fixed.

Passed:

- Startup waits for the firewall keeper to become healthy before app containers start. All seven app services share its network namespace; their namespace identifiers match.
- Public IPv4 HTTPS/HTTP, public IPv6 HTTPS, public DNS and Docker's embedded DNS fail from the protected namespace. Numeric loopback API requests still work.
- A disposable ordinary container can reach public HTTPS and a real Mac loopback HTTP test server. A probe sharing the Paca network namespace cannot reach the same destinations by numeric IP. This distinguishes firewall enforcement from a generally disconnected Mac or an unavailable destination.
- Firewall keeper permitted/effective/bounding capabilities are all zero after initialization; no-new-privileges is enabled. App containers lack NET_ADMIN/NET_RAW. No Docker socket, host network or NAS share is mounted in app services.
- Only Mac loopback TCP 8443 is published. Container input permits new non-loopback connections only on TCP 443, with established replies and loopback service traffic allowed. Docker auto-restart policies are disabled to avoid bypassing Compose health ordering after an engine restart.
- HTTPS validates with the generated public root certificate. UI HTML and health endpoint load. Admin login/password change, project/task creation and presigned attachment upload work with outbound access blocked.
- Six unit tests cover genuine SMB/NFS mount selection, rejection of a missing mount/local fallback, changed NAS identity, checksum verification, retained local queue on NAS outage, and a stopped application remaining stopped when a backup runs.
- Full backups create a readable custom PostgreSQL dump and a cold snapshot of named volumes. The app restarts healthy after the maintenance window. age encryption occurs locally; NAS copies are read back and verified before final rename.
- An actual user LaunchAgent invocation completed with exit code 0 and copied an encrypted archive to `/Volumes/Personal/Backups/Paca-OrbStack/<instance-id>/`. Configuration is every six hours and on mounts while logged in/awake. It does not auto-start the app.
- An encrypted archive was read back from the NAS, checksum-verified and decrypted using the separate recovery identity. Its state was restored into an isolated second Compose project's fresh volumes. The restored task, API key, private TLS CA and exact attachment bytes were verified through HTTPS on a different port. The test project's containers/volumes and plaintext recovery staging were removed afterward.

Implementation corrections found by real tests:

- OrbStack did not publish the browser port on an internal-only Docker network (`443/tcp` mapping was null). A regular bridge plus the namespace firewall preserves host access while explicitly denying new outbound connections, including LAN/host access.
- A launchd Python job stalled opening code under the protected Documents repository. Runtime code, credentials, logs and local archive queue now live under `~/Library/Application Support/Paca-OrbStack/`. The scheduled job was rerun successfully from that location without changing macOS privacy settings.
- Cold snapshot extraction needs writable parent-directory metadata even though the helper's root filesystem is read-only. `/snapshot` is a tiny tmpfs with actual state mounted in child named volumes. A repeated restore completed successfully with preserved numeric ownership.

The main instance is left running. Test-only projects/keys are removed from the main app after recovery verification. No Trello migration or existing agent reconfiguration was performed. The NAS runs no Paca services and receives only encrypted archives/checksums/target marker. Save the separate recovery identity outside this Mac before relying on the NAS copies for disaster recovery.
