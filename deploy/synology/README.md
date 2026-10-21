# Synology LAN evaluation bundle

Read [REVIEW.md](REVIEW.md) before starting. Current images have unresolved high/critical package scan findings. The owner's NAS has stock 4 GB RAM. This bundle is for disposable-data evaluation; keep primary work in Trello for now.

Complete deployment, local TLS trust, agent configuration, migration, backup/restore and update instructions are in [HOW_TO.md in the fork](https://github.com/tschleuss/paca/blob/synology-lan/HOW_TO.md).

Run `sh scripts/init.sh` once, then replace network placeholders in `.env`. Never copy a test `.env` or test `state/` from another host. Only the HTTPS gateway port is published. Agents execute on workstations; the NAS Docker socket is never mounted.

See [VALIDATION.md](VALIDATION.md) for completed checks and [security-scan.json](security-scan.json) for package scan results. Workstation MCP client dependencies are locked in `agents/package-lock.json` with security overrides in `agents/package.json`.
