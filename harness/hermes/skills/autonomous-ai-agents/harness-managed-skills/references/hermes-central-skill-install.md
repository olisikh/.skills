# Hermes central skill install and verification

Use this when a session establishes, migrates, or repairs the central-skills workflow for Hermes.

## Canonical layout

- Repo root: `~/.llm-harness`
- Portable skill source tree: `~/.llm-harness/harness/agents/skills/<skill>`
- Hermes skill source tree: `~/.llm-harness/harness/hermes/skills/<category>/<skill>`
- Target harness is determined by the containing `harness/<harness>/` directory
- Runtime install tree: `~/.hermes/skills/<skill>`

## Required installer behavior

`./harness.py install` must discover every directory containing `SKILL.md` under configured sources and flatten each installed target to the skill directory's basename. Source category paths may be nested; runtime skill directories must remain flat for Hermes compatibility.

## Cron coupling

If a scheduled job keeps `~/.llm-harness` current, it should:

1. work from `~/.llm-harness`
2. update repo state and submodules/sources as needed
3. run `./harness.py install`
4. report final `git status --short --branch`

## Verification recipe

1. Check that canonical repo paths exist.
2. Confirm the skill source lives under `~/.llm-harness/harness/<harness>/skills/...`.
3. Confirm any Hermes-targeted skill is under `~/.llm-harness/harness/hermes/skills/`.
4. Run `cd ~/.llm-harness && ./harness.py install`.
5. Verify runtime paths resolve into the repo, for example:
   - `~/.hermes/skills/autonomous-ai-agents/harness-managed-skills`
   - `~/.hermes/skills/autonomous-ai-agents/llm-harness-ops`
   - `~/.hermes/skills/software-development/hermes-agent-skill-authoring`
6. Confirm docs/instructions no longer describe `~/.agents` or `~/.hermes/skills` as the preferred physical source location for durable skills.
