---
name: limits
description: Check remaining LLM quota windows for CodexBar-enabled providers, formatted concisely for humans. This is a general CodexBar usage skill, not a Codex-specific skill.
---

# Limits

Use this skill when asked for current LLM limits, quota, remaining capacity, or whether Codex/OpenCode Go/Gemini/etc. are close to exhaustion.

## Default command

```bash
python ~/.agents/skills/mlops/limits/scripts/limits.py
```

When this skill is loaded in response to a limits/quota request, **execute the default command immediately** without asking the user for confirmation. Only deviate to filter by provider or output JSON if the user explicitly asks for those options.

The script queries CodexBar and prints one line per configured provider. If the channel supports Markdown, wrap the complete output in one fenced `text` code block.

## Options

```bash
python ~/.agents/skills/mlops/limits/scripts/limits.py --provider codex --provider opencodego
python ~/.agents/skills/mlops/limits/scripts/limits.py --json
```

## Notes

- Skill name is `limits`; in Hermes skill-slash form this is intended to be `/limits`.
- The canonical source path is `~/.llm-harness/local-skills/agents/mlops/limits`; the installed runtime path is `~/.agents/skills/mlops/limits`.
- For harness repository maintenance, use `cd ~/.llm-harness && ./harness.py update-repo` for a full refresh or `./harness.py update-skills` for configured submodule sources only; do not link or copy `update-skills.sh` into runtime homes.
