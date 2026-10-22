# Trello → Paca: Stash migration

## Open the imported board

Open Paca at **https://localhost:8443**, choose **Stash → Product Backlog → Stash board**.
The existing Table view is still available. The board loads cards progressively;
scroll/load more within a column to see the rest.

**You do not need a sprint.** Product Backlog holds the project's tasks without a
time-boxed iteration. The board groups them by status, matching your existing
continuous workflow. You can create a sprint later and assign a selected batch
of work to it; the migration leaves every task's sprint empty.

The imported workflow is:

| Status | Cards | Paca category |
| --- | ---: | --- |
| To-do | 188 | todo |
| Doing | 9 | inprogress |
| Agent Review | 1 | inprogress |
| Human Review/Feedback | 102 | inprogress |
| Done 🎉 | 214 | done |

## What was preserved

The 2026-10-22 import contains **514 cards**, **32 label definitions**, **63
checklists / 491 checkbox items**, and **1,019 comments**. Native Paca task numbers
match the Trello card numbers: Trello card 290 is now STAS-290. This worked because
the source numbers were contiguous and the destination had no tasks.

- Descriptions retain Markdown formatting, owners, acceptance criteria and links.
- Checklists are editable BlockNote checkboxes inside each task description,
  including original ordering and checked state (437 checked / 54 unchecked).
- Labels live in a **Labels** custom field with multiple colored options. Edit
  that field to change labels. The migration does not duplicate labels into tags.
  Trello's named color shades are mapped to explicit hex colors in the same families.
- Comments are separate, editable Paca comments in chronological import order.
  Their bodies record the original author and UTC timestamp. Paca's native author
  is the importing account and its native creation time is the migration time.
- Each task has the original Trello URL and number in custom fields. The tags
  `trello-import` and `trello-id-…` support reconciliation; keep them intact.
- Card order is preserved in the **Stash board** view. Other views have their own
  sorting and grouping.

Avatars, profile metadata, subscriptions, board backgrounds, Power-Ups and
non-comment activity history were omitted. The export had no attachments, dates,
archived cards or custom-field values to migrate. Existing Trello links inside
descriptions/comments remain original links; the private journal resolves source
card IDs to Paca task IDs. There is no ongoing two-way synchronization.

## Why the JSON export was supplemented

The board JSON had exactly 1,000 activity entries, including only 452 comments.
The connected Trello reader returned **1,019 comments** across 11 fully paginated
comment-activity pages. All 452 exported comments were present in that result.
The importer merged comments by original ID, recovering 567 older comments
without duplicating the exported ones. All recovered comments belonged to one
of the 514 exported cards.

For another board, obtain a fresh export and check whether activity is truncated.
`--comments` accepts a JSON array with `id`, `card_id`, `text`, `date`, and `author`
from a complete, paginated read. This migration script itself does not access
Trello; without that supplement it can import only comments in the JSON.

## Private files and backups

The source snapshot, supplemental comments, rich plan, ID journal and verification
report are outside Git at:

```text
~/Library/Application Support/Paca-OrbStack/migrations/stash-20261022/
```

`trello-export.json` is the untouched source snapshot. `plan.json` contains the
converted content. `journal.json` maps Trello card/comment IDs to Paca IDs and
records the board/status mapping. `verification.json` records the read-back audit.
These files contain private project content; do not commit or publish them.

The installed OrbStack backup controller includes `migrations/` in its encrypted
configuration bundle, alongside the database and application state. Temporary
browser cookie files and lock files are excluded. Backups are copied to the
existing verified NAS target under `/Volumes/Personal/Backups/Paca-OrbStack/`.
Keep the age recovery identity separately as described in the OrbStack guide.

## Reproduce or resume an interrupted import

This richer importer is **trello_migrate.py**. The older `trello_import.py` is a
minimal, text-only fallback with different behavior. Do not run both against
the same project. The rich importer is deliberately restricted to the five Stash
statuses; extend its explicit workflow mapping before using another workflow.
It stops on attachments, archived content or source custom-field values so those
cannot be silently lost.

From the repository root, install the locked workstation converter if missing:

```sh
npm ci --prefix deploy/synology/agents
```

Create an offline plan:

```sh
python3 deploy/synology/migration/trello_migrate.py /path/to/board.json \
  --comments /path/to/complete-comments.json \
  --output /private/path/plan.json
```

Review that plan and use a dedicated destination project. To apply it, add
`--apply --project-id PROJECT_UUID --journal /private/path/journal.json`.
For this installed OrbStack instance, `--local-admin` reads its existing `.env`
credentials into memory without printing them. Otherwise provide
`PACA_API_URL`, `PACA_API_KEY` and `--ca /path/to/root.crt` through your local
credential mechanism. Do not put credentials in a command, chat or tracked file.
API keys may need an associated user for native comment creation; the tested
Stash import used the local administrator's authenticated session.

The importer verifies titles, descriptions, checklist states, fields, statuses,
comments and view positions through the API. It reconciles cards using stable
Trello ID tags and comments using stable marker blocks, so a response lost before
journaling can be recovered on a rerun. It stops if imported content has changed,
if a previously imported item is missing, or if the project contains unrelated
tasks. **This is a resumable initial import, not a tool for updating a project
after people or agents start editing it.** Run only one import process at a time.

## Validation and next steps

Validation used ten focused unit tests, a disposable three-card / 79-comment
pilot, a second pilot pass and fresh-journal recovery with no duplicates, browser checks of the board,
colored labels and interactive checkboxes, and a full independent API read-back
of all 514 tasks and 1,019 comments. Column totals and all native task numbers
matched the source. The temporary pilot project was removed afterwards.

Trello was not changed, and **agent configuration has not been switched**.
Before a cutover, pause Trello writers, check for source changes since this
snapshot and reconcile those changes. Keep a single task system authoritative
afterward to avoid divergent copies.

For agents, use the pinned workstation MCP client described in the root
`HOW_TO.md`, this instance's HTTPS origin and public root CA, and the Stash
project's UUID from the private journal. Resolve status IDs from that journal or
the API. Labels are `custom_fields.labels` arrays; review stages are separate
statuses; checklists are description blocks. Read back every mutation. Use
`update_task` for status changes rather than the known-problematic MCP
`move_task` / `bulk_move_tasks` tools in this reviewed version. Update shared
Stash workflow instructions and each supported agent client's MCP configuration
in a separate cutover change. Superset worktrees, source files and terminal
sessions remain in their existing repositories/workspaces.
