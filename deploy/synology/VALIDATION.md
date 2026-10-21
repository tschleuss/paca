# Local validation — 2026-10-21

Baseline: upstream v0.19.1, with custom NAS Compose/Caddy/scripts and workstation MCP dependency overrides. Tested in OrbStack's Linux VM on this Mac, using native ARM64 variants of the pinned multi-platform image indexes. Each index was checked for NAS-compatible linux/amd64 support. This does not establish NAS performance or identical AMD64 package scan results.

## Passed

- Docker Compose configuration resolves; shell scripts parse. Secret generation produces private files and refuses to overwrite configuration.
- All seven services start; five upstream service healthchecks pass. RustFS initialization exits successfully.
- Only the gateway publishes a host port; test binding was 127.0.0.1:18443. No privileged container, host networking or Docker socket mount. Data services use an internal Docker network.
- Caddy configuration validates. HTTPS validates against its generated public root CA. UI HTML and API health endpoint return successfully.
- A separate non-loopback client container outside the configured trusted CIDR gets HTTP 403. The check is inside an explicitly ordered Caddy route, ahead of API/storage/web handle blocks. Actual NAS/router/guest-VLAN access rules still need on-device verification.
- Admin login, mandatory password change, project creation, task create/update/read-back.
- Presigned file upload through `/storage`, upload completion and later download of the exact bytes.
- Realtime Engine.IO polling transport handshake through `/ws/socket.io`. Full multi-browser event fanout was not exercised.
- A separate service-account key can read/write its permitted project; another project returns 403. The example project policy was exercised against the live local API.
- Released MCP package initializes over stdio and reads an authenticated task through HTTPS.
- Security-overridden MCP client (SDK 1.32.1, uuid 11.1.1) initializes, exposes 80 tools, creates/updates tasks, converts Markdown and reads the result back. This differs from upstream docs claiming 81 tools; do not rely on a fixed tool count.
- Four migration unit tests cover text/date/checklist/comment preservation, archived defaults, repeated-cursor protection, complete mapping validation and duplicate protection after journal loss.
- A synthetic Trello board imports into the live local API; a rerun creates no duplicate. Description content was read back. No real Trello exports were accessed.
- Cold backup script produces a logical dump, stopped-state archive and checksum, then restarts services.
- An isolated second Compose project restores the cold backup on a different HTTPS port. The existing API key, task and attachment bytes remain usable.
- A second restore starts with a confirmed empty PostgreSQL database, restores the logical dump with `--exit-on-error`, and recovers the task and attachment bytes from matching object-store state.

## Findings and fixes during validation

- The web image's Caddy binary has a NET_BIND_SERVICE file capability. Dropping every capability made it fail to execute. Adding only that capability fixed startup while keeping other capabilities dropped.
- A top-level Caddy response matcher was not sufficient ahead of `handle` blocks because of directive ordering. An explicit `route` now runs the source-network check first; the non-loopback denial test passed.
- Fresh logical restores must target a truly empty database, with API stopped. A Mac bind-directory rename reused a cached mount identity during the first attempt. A distinct fresh bind path and an empty-schema check fixed the test; these safeguards are in HOW_TO.md.
- Original MCP dependencies: npm audit reported one high and one moderate vulnerable package. The committed standalone client overrides both; the locked set's `npm audit --omit=dev` reports zero known findings as of this date. The test-only install allowed the reviewed new release despite local npm's two-day age policy; no global npm settings were changed. Deployment instructions retain the user's age policy.
- Docker Scout 1.24.0 scanned all seven local image variants for HIGH/CRITICAL findings. **The scans are not clean.** See security-scan.json and REVIEW.md. These are package matches, not a reachability assessment, and counts overlap between binaries/images. No application image was rebuilt or declared safe by these tests.

## Still required before primary use

Resolve/assess image findings, rescan NAS AMD64 images, confirm DSM/Container Manager compatibility and free memory, test allowed/blocked LAN paths and router rules, load-test representative concurrent agent work, verify full realtime collaboration, and perform a restore on the NAS or the intended recovery host. Audit all migration counts, assignments, dates, comments and attachment bytes before cutover.

No NAS deployment, production agent reconfiguration, real Trello migration or destructive Trello action occurred. The disposable local containers were stopped after validation. Only evaluation source files and sanitized scan summaries are committed; local secrets, state and backup archives are ignored by Git.
