---
name: llm-harness-ops
description: Manage ~/.llm-harness — add, move, register, and configure skills and harness homes. Canonical reference lives in docs/llm-harness-ops.md.
---

# llm-harness-ops

Use for adding or moving skills, registering submodules, changing harness mappings,
running setup, or fixing managed symlinks. Prefer the canonical guide:

[docs/llm-harness-ops.md](../../../../docs/llm-harness-ops.md)

## Core model

- First-party skills live under `harness/<harness>/skills/`; no config needed.
- External content comes only from configured Git submodules.
- `config.yaml` uses `version: 2` and a root `submodules:` mapping.
- Submodule path defaults to `submodules/<name>`; `path:` overrides exceptions.
- Export defaults are `from: skills` and `to: skills`.
- `to: skills` discovers `SKILL.md` directories and flattens their basenames.
- Any other `to` creates one exact file or directory link relative to harness home.
- `include` and `exclude` filter discovered skill paths; exclusion wins.
- Duplicate effective targets are errors.
- Matching new upstream skills install automatically after submodule updates.
- `setup:` commands run only through `./harness.py setup`.

## Add first-party skill

1. Create `harness/<harness>/skills/<skill-name>/SKILL.md`.
2. Run `./harness.py install`.
3. Verify target symlink.

## Register submodule

```sh
git submodule add <url> submodules/<name>
```

```yaml
submodules:
  <name>:
    exports:
      - harness: agents
```

Then run:

```sh
./harness.py update-skills submodules/<name>
./harness.py install
```

## Route subset elsewhere

Exclude exceptions from broad export and include them in specific export:

```yaml
exports:
  - harness: agents
    exclude:
      - category/claude-only
  - harness: claude
    include:
      - category/claude-only
```

## Exact export

```yaml
exports:
  - from: plugin/command.md
    harness: claude
    to: commands/plugin.md
```

## Setup and verification

```sh
./harness.py setup [submodule...]
python3 -m py_compile harness.py lib/*.py
./harness.py update-skills [submodule...]
./harness.py install
./harness.py audit-skills
./harness.py uninstall
git status --short
```

Do not edit installed runtime copies, track symlinks inside `harness/`, or edit
submodule contents unless intentionally maintaining a fork.
