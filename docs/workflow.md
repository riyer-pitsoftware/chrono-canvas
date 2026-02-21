# Task Tracking Workflow (Beads)

ChronoCanvas uses [beads](https://github.com/unused/beads) (`bd`) for all task tracking. Issues live in `.beads/` (git-tracked), so the full project history travels with the repo.

**Rule**: create a bead before writing code. Never use `TodoWrite`, `TaskCreate`, or markdown to-do lists for task tracking.

---

## Why beads?

- Issues are plain files in `.beads/` — no external service, no token required
- Git hooks auto-sync on every commit, so issue state is always in version control
- Agents and humans share the same issue queue with no friction

---

## Priority system

| Label | Meaning |
|-------|---------|
| P0 | Critical — production broken or blocking all work |
| P1 | High — important, do soon |
| P2 | Medium — normal priority |
| P3 | Low — nice to have |
| P4 | Backlog — someday/maybe |

Pass priority as an integer (`--priority=0`) or as `P0`–`P4`.

---

## Command reference

### Finding work

```bash
bd ready                        # issues with no blockers (start here)
bd list --status=open           # all open issues
bd list --status=in_progress    # what's being worked on
bd show <id>                    # full detail + dependencies
bd stats                        # counts by status
bd blocked                      # issues waiting on others
```

### Creating issues

```bash
bd create \
  --title="Short imperative summary" \
  --description="Why this exists and what needs to be done" \
  --type=task|bug|feature \
  --priority=2
```

Types: `task`, `bug`, `feature`. Always provide `--description`; one-liners are not enough for agents to act on without context.

### Updating issues

```bash
bd update <id> --status=in_progress   # claim work before starting
bd update <id> --status=open          # release without closing
bd update <id> --title="..."          # edit title inline
bd update <id> --description="..."    # edit description inline
bd update <id> --notes="..."          # add notes
bd update <id> --assignee=username
```

**Do not use `bd edit`** — it opens `$EDITOR` which blocks agents.

### Closing issues

```bash
bd close <id>                          # mark complete
bd close <id> --reason="explanation"   # close with context
bd close <id1> <id2> <id3>            # close multiple at once
```

### Dependencies

```bash
bd dep add <issue> <depends-on>   # issue cannot start until depends-on is closed
```

`bd ready` excludes issues that have open blockers, so dependencies are automatically enforced.

### Sync

```bash
bd sync              # push/pull .beads/ changes with remote
bd sync --status     # check sync state without syncing
```

Git hooks run `bd sync` automatically on commit. Run it manually at session end to be safe.

---

## Session workflow

```
1. bd ready                              # find available work
2. bd show <id>                          # read the description
3. bd update <id> --status=in_progress   # claim it
4. ... write code ...
5. bd close <id> --reason="..."          # mark complete
6. git add <files>
7. bd sync                               # commit bead state
8. git commit -m "..."
9. bd sync                               # pick up any new bead changes
10. git push
```

For multi-issue sessions, repeat steps 1–5 for each issue, then do a single add/sync/commit/push at the end.

---

## Project conventions

- **Always create a bead before writing code.** The issue is the source of truth for why a change exists.
- **Claim with `in_progress` before starting.** This prevents two agents from picking up the same issue.
- **Close with a reason.** `--reason` becomes the permanent record of what was done and why.
- **Parallel creation.** When creating many related issues at once, run `bd create` calls in parallel (e.g. via subagents) rather than sequentially.
- **No markdown task lists.** Don't use `- [ ]` checklists in files or `TodoWrite` / `TaskCreate` tools. Beads is the only task tracker.
- **Dependency hygiene.** Before closing an issue that blocks others, check `bd blocked` to see what gets unblocked.

---

## Issue ID format

Beads assigns short random IDs like `history-faces-6it` or `history-faces-omg`. The prefix (`history-faces`) is the project slug. Refer to issues by their short suffix (`6it`, `omg`) in conversation; use the full ID in git commit messages and `--reason` strings for traceability.

---

## Git integration

`.beads/` is committed alongside source code. The hooks in `.beads/hooks/` (if present) run `bd sync` automatically on `git commit`. If hooks are not installed, run `bd doctor` to diagnose and `bd sync` manually at session end.

```bash
bd doctor    # check hook installation and sync health
```
