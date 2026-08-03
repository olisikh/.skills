---
title: LLM Harness Operations Guide
summary: How to add, move, register, and configure skills and harness homes.
tags: [llm-harness, operations, skills]
updated: 2026-08-03
confidence: high
---

# LLM Harness Operations Guide

Canonical reference for changing `~/.llm-harness` structure and configuration.

## Repository model

`llm-harness` links repository-managed files into runtime homes such as
`~/.agents`, `~/.claude`, and `~/.config/opencode`.

```text
config.yaml             # external submodule exports
harness-paths.yaml       # non-default harness home paths
harness/<name>/          # first-party harness content
submodules/<name>/       # external Git submodules
state/                   # installation audit state
```

First-party skills need no configuration. Put them below:

```text
harness/<harness>/skills/<optional-category>/<skill-name>/SKILL.md
```

Installed standard skill targets are always flat:

```text
<harness-home>/skills/<skill-name>
```

Other top-level entries below `harness/<harness>/` map directly into harness home.

## Configuration

`config.yaml` uses schema version 2:

```yaml
version: 2

skill_mirrors:
  claude:
    from: agents

submodules:
  example-skills:
    exports:
      - harness: agents
```

### Submodule paths

Submodule `example-skills` defaults to physical path
`submodules/example-skills`. Override unusual layouts:

```yaml
submodules:
  example-skills:
    path: vendor/example
```

Configured paths must be safe repo-relative paths and must appear in `.gitmodules`.

### Skill collection exports

Export defaults:

```yaml
- from: skills
  harness: agents
  to: skills
```

`to: skills` has reserved behavior:

1. Walk `from` recursively.
2. Discover directories containing `SKILL.md`.
3. Stop below each discovered skill directory.
4. Apply export filters.
5. Link each directory to `skills/<directory-basename>`.

`harness` is always required. `from` and `to` default to `skills`.

### Filters

`include` and `exclude` match discovered skill paths relative to `from`:

```yaml
exports:
  - harness: agents
    exclude:
      - deprecated/
      - claude/special-skill

  - harness: claude
    include:
      - claude/special-skill
```

Rules:

- Missing `include` includes every discovered skill.
- Missing `exclude` excludes nothing.
- Exclusion wins.
- A trailing `/` matches a subtree.
- `*`, `**`, `?`, and character classes are supported.
- An unmatched literal include is an error.
- An export selecting no skills emits a warning.

When routing exceptions elsewhere, exclude them from broad export and include
them in specific export. Duplicate targets are errors.

### Exact exports

Any `to` other than exact value `skills` creates one exact symlink. Source may
be file or directory; destination is relative to harness home:

```yaml
submodules:
  example-plugin:
    exports:
      - from: plugin/command.md
        harness: claude
        to: commands/example.md
      - from: plugin/references
        harness: claude
        to: skills/example/references
```

Filters are invalid on exact exports. Missing sources are errors.

### Setup commands

Setup is explicit and never runs during ordinary install:

```yaml
submodules:
  example-tool:
    setup:
      - uv tool install --editable .
      - example-tool --version
```

Run all or selected setup declarations:

```bash
./harness.py setup
./harness.py setup example-tool
```

Commands run directly in submodule checkout without a shell.

### Mirrors

Mirrors expose standard skills selected for one harness in another:

```yaml
skill_mirrors:
  claude:
    from: agents
```

Mirrors apply only to standard flattened skill directories. Direct/mirror
collisions are errors.

## Workflows

### Add first-party skill

```bash
mkdir -p harness/agents/skills/my-skill
cat > harness/agents/skills/my-skill/SKILL.md <<'EOF'
---
name: my-skill
description: Does one useful thing.
---

# my-skill
EOF
./harness.py install
```

### Register external submodule

```bash
git submodule add https://github.com/example/skills.git submodules/example-skills
```

```yaml
submodules:
  example-skills:
    exports:
      - harness: agents
```

Then:

```bash
./harness.py update-skills submodules/example-skills
./harness.py install
```

### Move first-party skill

Move source directory between harness trees, then install:

```bash
mv harness/agents/skills/my-skill harness/claude/skills/
./harness.py install
```

### Exclude upstream skill

Add source-relative path to export `exclude`, then run `./harness.py install`.
Stale managed target is removed.

### Add harness path

Default path is `~/.<harness>`. Add exceptions to `harness-paths.yaml`:

```yaml
harness:
  opencode: ~/.config/opencode
```

## Commands

```bash
./harness.py install
./harness.py uninstall
./harness.py update-skills [submodule-path...]
./harness.py setup [submodule-name...]
./harness.py audit-skills
./harness.py audit-readiness [--project PATH]
./harness.py update-repo
```

`install` validates complete target graph before changing links. It warns and
preserves existing real paths or external symlinks. Managed stale symlinks are
removed. Each harness home stores managed target names in
`.llm-harness-managed-targets.json`; cleanup never guesses ownership by scanning
unrelated home content. Duplicate or overlapping target ownership fails validation.

`update-skills` updates configured pinned commits. New upstream skills matching
broad exports install automatically when links refresh.

`audit-skills` repairs safe repo-managed mismatches and records complete/blocked
state with full harness-relative targets in `state/skill-installation.json`.

## Verification

After structural changes:

```bash
python3 -m py_compile harness.py lib/*.py
python3 -m unittest discover tests
./harness.py update-skills
./harness.py install
./harness.py audit-skills
./harness.py uninstall
git status --short
```

Do not overwrite unrelated real files or external symlinks. Do not edit runtime
copies or submodule contents unless intentionally maintaining upstream code.
