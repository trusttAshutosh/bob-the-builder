# Mobile Cursor relay (Bob + approvals)

When `bob validate-ticket` or Cursor Agent runs long shell steps, the IDE may wait for **Approve**. If you are away from the desk, use **Cursor Mobile Relay** - local, $0.

## Location

`Desktop/cursor-mobile-relay` (separate git repo - not part of bob-the-builder).

## Quick start

1. Cursor launched with `--remote-debugging-port=9222`
2. From relay folder: `scripts/start.ps1` (after `.env` with `RELAY_PASSWORD`)
3. Tailscale: `tailscale serve --bg --https=443 http://127.0.0.1:8787`
4. Phone browser: `https://YOUR-PC.tailnet.ts.net/?token=PASSWORD`

## Bob-specific notes

- Relay does **not** replace Bob - it only forwards view/approve to your running Cursor session
- Start `bob validate PE-123` in Cursor chat at desk; approve Gradle/bootRun prompts from phone
- Bob proof artifacts still land in `docs/tdd-runs/<id>/REPORT.md` on the host repo

## Docs

- Relay README: `Desktop/cursor-mobile-relay/README.md`
- Workflow cheat sheet: `cursor-markdowns/WORKFLOW.md` (mobile section)
- Backup copy: `cursor-markdowns/MOBILE_RELAY.md`

## Optional

`GCHAT_WEBHOOK_URL` in relay `.env` posts a Google Chat alert when Cursor needs approval.
