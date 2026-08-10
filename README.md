# llm-harness

Personal harness hub for LLM skills and harness-specific home files.

## Layout

```text
llm-harness/
├── AGENTS.md                  # repo contributor rules
├── harness/                   # harness-specific home files and first-party skills
│   ├── agents/                # mirrors ~/.agents/
│   │   └── skills/             # first-party portable skills
│   ├── claude/                # mirrors ~/.claude/
│   │   └── CLAUDE.md
│   ├── opencode/              # mirrors ~/.config/opencode/
│   ├── hermes/                # mirrors ~/.hermes/
│   └── codex/                 # mirrors ~/.codex/
├── docs/
│   └── llm-harness-ops.md     # canonical operational guide
├── harness-paths.yaml         # non-obvious harness root overrides
├── harness.py                 # unified entrypoint
├── lib/                       # Python implementation
├── scripts/                   # automation helpers
├── submodules/                # shared upstream skill submodules
│   ├── obsidian-skills
│   └── mattpocock-skills
└── config.yaml                # skill source mapping rules
```

## Install model

Run from `~/.llm-harness`:

```bash
./harness.py install
```

Installer behavior:

- discovers harnesses from `harness/`, `harness-paths.yaml`, and `config.yaml`
- maps harness homes by convention:
  - `agents` -> `~/.agents`
  - `claude` -> `~/.claude`
  - `codex` -> `~/.codex`
- reads `harness-paths.yaml` for non-obvious roots like OpenCode and custom Hermes skill installs
- reads configured skill sources from `config.yaml` and discovers first-party standard skills under `harness/<name>/skills/`
- symlinks every directory containing `SKILL.md` into target `skills/`, flattening nested source categories to the final skill directory name
- ignores arbitrary files and directories under `harness/<name>/skills/` that do not contain `SKILL.md`
- symlinks non-skill top-level files and directories from `harness/<name>/` 1:1 into target harness home
- removes stale managed symlinks
- warns and skips when target path already exists and is not matching expected symlink

To remove managed symlinks later:

```bash
./harness.py uninstall
```

## Operations

For step-by-step recipes on adding skills, registering shared sources, moving skills between harnesses, and troubleshooting, see [docs/llm-harness-ops.md](docs/llm-harness-ops.md).

There is also a local skill, `llm-harness-ops`, that provides a guided workflow for managing this repository.

## Skill source sync

Shared external skill sources live as git submodules; the LLM Wiki v2 is maintained as a first-party source under `harness/agents/skills/research/wiki/`:

- `obsidian-skills`
- `mattpocock-skills`

Update submodule pointers with:

```bash
./harness.py update-skills
```

Optional commit/push flow:

```bash
./harness.py update-skills --commit --push
```

Sync rules:

- `config.yaml` defines shared/external exports under `submodules:`; first-party standard skills live under `harness/<name>/skills/`
- `harness.py update-skills` updates configured pinned submodule commits, then refreshes managed symlinks in target harness homes and removes stale managed links
- `harness.py audit-skills` repairs safe wrong managed symlinks, verifies every effective configured skill resolves to its canonical source, and records the complete/blocked inventory in `state/skill-installation.json`
- exports targeting `skills` recursively discover `SKILL.md` directories and flatten them; exact exports can link any file or directory to a harness-relative target
- export-local `include` and `exclude` lists select harness-specific subsets; newly matched upstream skills install automatically
- duplicate effective targets are configuration errors rather than order-dependent overrides
- `harness.py update-repo` runs the audit after its pull/update cycle and commits/pushes state changes, so newly discovered skills and corrected installs become durable repository state
- install-time mapping of configured skills to target harness homes is controlled by `config.yaml`; harness-local skills target their containing harness
- `harness.py setup [submodule...]` explicitly runs setup commands; ordinary install never executes them

## User-owned skill data

`config.yaml` controls installation and routing only. Non-secret, user-owned settings
and durable agent artifacts live under `~/.agents/`:

- `~/.agents/config/skill-paths.json` — configured vault and artifact paths;
- `~/.agents/handoffs/`, `research/`, `reports/`, `learning/`, `writing/`, and
  `questionnaires/` — durable portable artifacts.

The tracked source for `skill-paths.json` is `harness/agents/config/`; the
installer exposes it at `~/.agents/config/skill-paths.json`. Do not store API
tokens, passwords, or other secrets there.

Audit declared prerequisites without mutating runtime state:

```bash
./harness.py audit-readiness
./harness.py audit-readiness --project /path/to/project
```

`audit-skills` verifies symlink installation; `audit-readiness` reports whether
declared paths, binaries, credentials, and per-project setup documents are ready.

## Notes

- canonical checkout path is `~/.llm-harness`
- configured skill sources and `harness/<name>/skills/` first-party skills are symlinked directly to target harness homes
- shared skill submodules live under `~/.llm-harness/submodules/<submodule>`
- first-party skills live under `~/.llm-harness/harness/<harness>/skills/`
- harness-specific non-skill files live under `~/.llm-harness/harness/<name>/`
- Hermes package-bundled skills stay in the Hermes install/source tree, not in `llm-harness`
- OpenCode will discover both `~/.agents/skills` and `~/.config/opencode/skills`
- Claude portable-skill auto-discovery is deferred for now
