# LLM Wiki v2 contract

This reference is the portable copy of the contract stored at
`WIKI_ROOT/90 System/schema.md`.

## Source of truth

- Markdown body and YAML frontmatter are authoritative.
- `90 System/registry.json` is a rebuildable ID/path/metadata index.
- `80 Maps/` is human navigation generated from frontmatter.
- `90 System/legacy-path-map.json` translates paths from the pre-v2 topic tree.
- `99 Archive/` is preserved history and is excluded from normal recall.

## Root placement

| Root | Meaning | Mutability |
|---|---|---|
| `00 Inbox/` | unprocessed captures | agent/human |
| `10 Sources/` | immutable articles, repositories, papers, notes, data | append-only |
| `20 Knowledge/` | flat concepts, topics, references, theses, decisions | maintained |
| `30 Projects/` | active delivery work | maintained |
| `40 Outputs/` | generated reports/artifacts | generated |
| `80 Maps/` | domain/status navigation | generated |
| `90 System/` | schema, registry, logs, sessions, migration state | generated/operational |
| `99 Archive/` | compatibility preservation | quiet |

## Frontmatter

`id`, `title`, `kind`, `domains`, `tags`, `status`, `created`, `updated`, and
`source_refs` are required for active notes. `summary`, `aliases`,
`confidence`, and `external_refs` are strongly recommended. A source may additionally
carry `source_type`, `source_url`, and `ingested`.

Stable IDs are lowercase hyphen-separated values. IDs do not encode the current
folder path, so moving a note does not break its identity. `domains` are
controlled broad areas; `tags` are more specific searchable terms.

## Linking and evidence

New notes use `[[Title]]` wikilinks. A factual answer should cite the exact note
path and follow `source_refs` when provenance matters. Historical path references
are resolved through the legacy map during the migration window.

## Rebuild

The first-party deterministic helper can rebuild the registry and Maps and can
validate duplicate IDs, required metadata, missing registry targets, and legacy
path links. Rebuilding derived files must not modify source notes.
