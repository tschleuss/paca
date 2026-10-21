# Paca on the Synology DS1821+: review

Reviewed 2026-10-21. Baseline: **v0.19.1**, commit `984030d2529a575656d0c696eacd0b1e7e4ed2c7`.

## Recommendation

**Suitable for disposable-data LAN evaluation; not recommended for primary work yet.** Current image scans report high-severity package findings across the stack, including critical records in some images. Network hardening reduces exposure but does not repair vulnerable application dependencies. Use the NAS for the task system and run coding agents on workstations. Do not put the upstream Docker-socket agent runner on a NAS containing important storage. Keep Trello available until migration reconciliation, a restore drill and a representative workload trial succeed.

This is a targeted source/configuration review and local functional test, not a penetration test, a complete dependency audit, or a guarantee of reliability. The user confirmed stock 4 GB installed RAM. No NAS login, available-memory measurement, or NAS deployment was available. No real Trello data or existing agent settings were changed. See VALIDATION.md and security-scan.json for test/scan evidence.

## Trust and maintenance

The repository is public under Apache-2.0. GitHub reports creation on 2026-03-20: about seven months old. It has active releases, external contributions, dependency update activity, API/authorization tests, integration/e2e workflows, and a private security reporting policy. Contributions are heavily concentrated in one maintainer (GitHub API returned 1,715 contributions for the lead versus 137 for Copilot and much smaller individual totals). That is meaningful maintenance risk, not evidence of bad intent.

Eleven published security advisories are significant. They cover serious authorization, SSRF, filesystem and plugin database isolation failures. Publishing fixes and regression tests is positive; the number and recency mean this is not yet a mature, low-maintenance replacement for Trello. The listed fixed versions are all at or below v0.19.0. v0.19.1 is the current release at review time; this comparison does not establish that no undiscovered or dependency vulnerabilities remain.

| Advisory | Severity | Listed fixed version | Problem |
|---|---|---|---|
| [GHSA-7f97-wf96-gmjm](https://github.com/Paca-AI/paca/security/advisories/GHSA-7f97-wf96-gmjm) | high | v0.19.0 | Agent key authentication could grant instance administrator privileges |
| [GHSA-f2mf-mg99-22w5](https://github.com/Paca-AI/paca/security/advisories/GHSA-f2mf-mg99-22w5) | high | v0.18.6 | Email plugin function could bypass internal-network request protections |
| [GHSA-vp6r-f2jv-9p9q](https://github.com/Paca-AI/paca/security/advisories/GHSA-vp6r-f2jv-9p9q) | high | v0.18.4 | Plugin SQL filtering could permit database-container execution and file reads |
| [GHSA-ph34-wrxh-vwxc](https://github.com/Paca-AI/paca/security/advisories/GHSA-ph34-wrxh-vwxc) | high | v0.18.4 | Plugin uninstall path validation could allow unintended file deletion |
| [GHSA-x5v3-9j39-fq73](https://github.com/Paca-AI/paca/security/advisories/GHSA-x5v3-9j39-fq73) | medium | v0.18.4 | SQL expression wrapping could expose credentials despite plugin result redaction |
| [GHSA-hjcj-373w-vq8m](https://github.com/Paca-AI/paca/security/advisories/GHSA-hjcj-373w-vq8m) | critical | 0.16.0 | Legacy administrator token mapping could bypass project permissions |
| [GHSA-cj3q-c44j-q8p9](https://github.com/Paca-AI/paca/security/advisories/GHSA-cj3q-c44j-q8p9) | high | 0.14.1 | IPv6 transition addresses could bypass request destination restrictions |
| [GHSA-xwmv-9c7h-g947](https://github.com/Paca-AI/paca/security/advisories/GHSA-xwmv-9c7h-g947) | high | 0.14.1 | Unverified resource IDs could expose or modify other projects' documents and files |
| [GHSA-xxc8-ggm7-vmxp](https://github.com/Paca-AI/paca/security/advisories/GHSA-xxc8-ggm7-vmxp) | high | 0.16.1 | Agent creation could attach unauthorized roles |
| [GHSA-mx24-j477-c5cm](https://github.com/Paca-AI/paca/security/advisories/GHSA-mx24-j477-c5cm) | high | 0.16.1 | Document-file ownership checks could allow cross-project file access and changes |
| [GHSA-g6mx-8g92-w9v5](https://github.com/Paca-AI/paca/security/advisories/GHSA-g6mx-8g92-w9v5) | critical | 0.14.1 | Plugin database functions could bypass project isolation |

## Code and architecture findings

- The core needs PostgreSQL, Valkey, S3-compatible storage, a Go API, realtime service, static web server, and gateway. This is seven long-running containers, not a single tiny app. The storage initialization job exits after setting ownership.
- The production deployment mounts `/var/run/docker.sock` into the agent runner, which creates agent sandboxes and Docker-in-Docker sidecars. This expands host control and resource consumption substantially. Our Compose file omits that service entirely.
- API startup applies embedded database migrations automatically. Upgrades can change persistent state as soon as a new API starts. Rolling back an image alone is not a reliable rollback.
- The API drops to its `app` user after directory ownership setup. PostgreSQL/Valkey have initialization entrypoints; this deployment does not force arbitrary UIDs that would break those entrypoints. `no-new-privileges`, selected capability removal, resource limits, and bounded logs reduce exposure. These are container controls, not a VM boundary.
- Authentication uses stored hashed API keys, session cookies/JWTs, and a centralized authorization principal. v0.19 introduced resource-based roles. Human API keys carry the human's permissions: use separate service accounts for agents.
- Plugin MCP modules are executable JavaScript dynamically loaded into the agent's local process (`apps/mcp/src/plugin-loader.ts`). Backend WASM sandboxing does not sandbox that local JavaScript. Install no plugins during the pilot; review frontend/MCP/backend code and permissions before enabling any later.
- The default API CORS fallback is `*`; our deployment explicitly supplies the HTTPS origin to both API and realtime. Login rate limiting remains enabled and cookies require HTTPS.
- The internal Docker network removes normal internet routing from the API/database/storage/realtime/web services. It is not a complete host/LAN isolation boundary. Gateway has a separate bridge for the published HTTPS port. Host firewall/VLAN controls still matter. Webhooks, outbound email, marketplace downloads, cloud GitHub/SSO and in-NAS LLM calls will not work without an intentional networking change.
- Object storage presigned URLs are rewritten to `/storage`, with the original internal Host restored by Caddy for signature validation. Keep these proxy details intact.
- No obvious analytics SaaS integration surfaced in the targeted source search. This was not an exhaustive outbound traffic audit. Calling an external AI provider from workstation agents still sends the context they use to that provider; local hosting does not make AI inference offline.
- **Open functional defect:** [issue #610](https://github.com/Paca-AI/paca/issues/610) describes `move_task` / `bulk_move_tasks` falsely reporting task moves. Avoid both at this baseline. Change status/sprint via `update_task`, then read the task back. Read all pagination cursors; tool defaults do not return the entire board.

## Current image scan findings: reason to defer production

Docker Scout scanned all seven pulled ARM64 image variants at the recorded digest indexes, filtering to HIGH/CRITICAL. It reports package/version matches, **not demonstrated exploitability**. For example, PostgreSQL findings include a Go-compiled privilege-switching helper; these are not all PostgreSQL engine defects. Source review and reachable-code analysis are still required. A NAS AMD64 scan may differ.

| Service | Finding records | Distinct advisory IDs | Critical records |
|---|---:|---:|---:|
| api | 9 | 9 | 0 |
| web | 17 | 12 | 3 |
| realtime | 6 | 6 | 0 |
| rustfs | 2 | 2 | 0 |
| postgres | 36 | 36 | 4 |
| valkey | 1 | 1 | 0 |
| gateway | 17 | 12 | 3 |

The API findings include `golang.org/x/image` 0.44.0 (scanner fix 0.45.0), `x/text` 0.40.0 (0.41.0), `x/crypto` 0.52.0 (through 0.56.0), and Alpine OpenSSL/zlib packages. Other images also have current findings. See [security-scan.json](security-scan.json) for exact IDs, affected package versions, fix versions and scanner links. Counts overlap between images and can include the same advisory in multiple installed binaries; do not add these into an alleged number of exploitable bugs.

**Do not interpret the hardened network as a fix for these findings.** Before migrating primary work, use refreshed upstream releases or reproducibly rebuilt patched images and rerun scans plus functional tests, or document why individual findings are unreachable with adequate evidence. We have not patched or rebuilt the NAS application images in this task. The deployment assets are ready for isolated evaluation, not an assertion that these images are safe for important production data.

## NAS sizing

The [Synology datasheet](https://global.download.synology.com/download/Document/Hardware/DataSheet/DiskStation/21-year/DS1821%2B/enu/Synology_DS1821%2B_Data_Sheet_enu.pdf) lists an AMD Ryzen V1500B, four cores at 2.2 GHz, 4 GB stock RAM and up to 32 GB supported RAM. Its x86_64 CPU matches the verified `linux/amd64` image manifests in `images.lock.json`. No GPU or local LLM is required for this deployment.

**Sizing judgment, not a NAS benchmark:** your confirmed stock 4 GB could support a very small board trial if little else runs, but I do not recommend primary use alongside your existing NAS services. Aim for 8 GB or more and at least 3–4 GB free before starting; 16 GB gives more headroom. The running-service memory ceilings total 3,328 MiB, plus the short-lived 128 MiB initialization job. DSM, caches, other services and backup compression need additional memory. Ceilings prevent runaway use; they do not reserve RAM or prove workload capacity.

[RustFS documents at least 1 GB for testing](https://docs.rustfs.com/en/installation/requirement/checklists/hardware-selection). The upstream storage image is **1.0.0-rc.6**, a release candidate: an additional maturity risk. Its published enterprise production sizing is aimed at large distributed storage; this is a small single-node attachment store. We retained the upstream-compatible store instead of introducing an untested replacement.

Local testing on this Mac's OrbStack Linux VM used native ARM64 images from the same multi-platform manifests. A short idle sample for all seven services was approximately 207 MiB total container memory. That excludes VM/host cache overhead and is not sustained-load or DS1821+ evidence. CPU, DB cache, attachments, concurrent agents and long histories can change consumption. Measure actual NAS load before expanding use.

Use the regular Btrfs/RAID volume for persistent data, not a volatile cache directory or SMB-mounted database directory. Disk capacity should include attachments, database growth, Docker images and backups. Start with at least 10–20 GB free for a pilot (planning estimate) and monitor it. RAID protects availability, not accidental deletion, ransomware or failed upgrades.

## Evidence and follow-up

- [Release and exact source](https://github.com/Paca-AI/paca/releases/tag/v0.19.1)
- [Security policy](https://github.com/Paca-AI/paca/blob/v0.19.1/SECURITY.md)
- [Production Compose](https://github.com/Paca-AI/paca/blob/v0.19.1/deploy/docker-compose.prod.yml)
- [Authentication implementation](https://github.com/Paca-AI/paca/blob/v0.19.1/services/api/internal/transport/http/middleware/authn.go)
- [MCP plugin loading](https://github.com/Paca-AI/paca/blob/v0.19.1/apps/mcp/src/plugin-loader.ts)
- [Release pipeline](https://github.com/Paca-AI/paca/blob/v0.19.1/.github/workflows/cd.yml): multi-architecture images and npm provenance; these are supply-chain signals, not a source audit. Digest pinning prevents tag drift but does not authenticate a publisher by itself.
- [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/) and [firewall behavior](https://docs.docker.com/engine/network/firewall-iptables/)

The original released MCP npm dependency set produced two vulnerable-package findings (SDK high, uuid moderate). Our standalone workstation client manifest overrides SDK to 1.32.1 and uuid to 11.1.1, with a committed npm lockfile. The resulting audit had zero known findings on this date and passed stdio read/write/Markdown tests. This does not patch any NAS image. SDK advisory applicability varies: some concern HTTP transports or experimental task stores unused by this stdio setup; the score alone does not prove a reachable exploit. Sources: [SDK task isolation advisory](https://github.com/advisories/GHSA-22jm-h49p-29qw), [SDK redirects advisory](https://github.com/advisories/GHSA-6prh-2h8m-c8cw), [uuid advisory](https://github.com/advisories/GHSA-w5hq-g745-h8pq).

Before trusting important work: test two concurrent agents editing/reading tasks, restart the NAS stack, restore a backup elsewhere, check authorization with a restricted account, verify uploads/downloads and every imported list's counts. Check advisory and release pages at every upgrade. Resolve or assess the recorded image findings and rerun dependency/image scans before treating the setup as a long-term production service; a clean scan is not proof of safety.
