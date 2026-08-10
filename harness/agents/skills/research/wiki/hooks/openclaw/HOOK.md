---
name: wiki-session
version: 2.0.0
description: "Capture redacted OpenClaw session context under the configured LLM Wiki v2 root."
metadata: {"openclaw":{"emoji":"📚","events":["command:new","command:reset"],"async":true}}
---

# Wiki v2 session hook

At the end of an OpenClaw session, write a redacted digest under
`WIKI_ROOT/90 System/.sessions/digests/` and high-signal feedback candidates
under `WIKI_ROOT/90 System/.sessions/feedback/`.

The hook resolves `WIKI_ROOT` from `~/.config/llm-wiki/config.json`. It never
uses the removed `~/.llm-wiki` checkout, copies full transcripts, or promotes
session material into `20 Knowledge/` automatically.

## Safety

- Only write below `90 System/.sessions/`.
- Redact API keys, tokens, passwords, cookies, and opaque blobs.
- Swallow hook errors by default; set `WIKI_SESSION_HOOK_DEBUG=1` for diagnostics.
