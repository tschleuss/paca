# OrbStack validation — 2026-10-22

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
