# Rule: update the doc index when adding or renaming files

When you create or rename a file in a folder that contains a `CLAUDE.md`, update that `CLAUDE.md` to include the new file in its doc index (or remove the renamed-away entry). Do not skip this step.

**Why:** per-folder `CLAUDE.md` files are auto-loaded when an agent enters that folder. If the doc index drifts from reality, future sessions either miss the new doc entirely or chase stale links.

**Scope:**
- Applies to any file added under a folder whose `CLAUDE.md` contains a doc index, doc map, or file listing.
- Renames count too — both the old entry and the new entry need attention.
- Also applies to index tables inside README files that serve as an index (e.g., the decision-log "Current decisions" table).
- Does not apply to ephemeral files (`.DS_Store`, build artifacts, lockfiles) or gitignored pipeline data under `leads/`.

**Skip when:**
- The folder's `CLAUDE.md` intentionally references contents in aggregate ("all dated signal files land here") rather than listing files individually — most agent-output folders work this way.
- The file lands in a folder with no `CLAUDE.md` of its own.

**How to apply:**
- After writing a new file at `<folder>/<new-file>.md`, look for `<folder>/CLAUDE.md` (and the nearest ancestor `CLAUDE.md` with an index) and add an entry.
- After moving a file, update both the source folder's index (remove) and the destination folder's index (add), if both exist.
- Agents that write dated output files follow their runbook's convention — if the runbook says "no index entry for dated files," that wins.
