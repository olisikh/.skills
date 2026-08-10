# v2 migration and maintenance protocol

This is an implementation reference, not a user-facing command list.

## Migration invariants

1. Back up Git history before a migration.
2. Inventory every old content note before moving it.
3. Preserve immutable source bodies and record `legacy_path`.
4. Generate stable IDs before rewriting links.
5. Rewrite old relative Markdown links to canonical Obsidian wikilinks only
   after the complete old-path map exists.
6. Rebuild the registry and Maps, then validate them.
7. Archive the old tree only after the new tree passes validation.
8. Keep the old-to-new path map until all consumers have cut over.

## Source mapping

- `topics/<topic>/raw/articles` → `10 Sources/Articles`
- `topics/<topic>/raw/repos` → `10 Sources/Repositories`
- `topics/<topic>/raw/papers` → `10 Sources/Papers`
- `topics/<topic>/raw/notes` → `10 Sources/Notes`
- `topics/<topic>/raw/data` → `10 Sources/Data`
- `topics/<topic>/wiki/*` → flat `20 Knowledge/`; the old category becomes
  `kind` metadata.
- `topics/<topic>/output` → `40 Outputs`
- topic inboxes → `00 Inbox`
- old logs and session state → `90 System/`
- old topic guides → `99 Archive/Legacy Guides/`

The old topic slug becomes a domain or tag. Cross-domain notes are represented
once, with multiple metadata values.

## Runtime cutover

The config file remains `~/.config/llm-wiki/config.json`, but `hub_path` points
to the v2 root, not a nested `hub/` directory. OpenClaw indexes the active root
and loads the hook from the first-party harness skill. Cron maintenance receives
its resolved `repo`, `root`, and scoped Git prefix from its preparation script;
it must not guess paths from a prompt or stage outside the Wiki prefix.
