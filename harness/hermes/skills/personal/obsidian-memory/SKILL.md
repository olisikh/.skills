---
name: obsidian-memory
description: Use when a question depends on Oleksii's notes or personal context. Search the full Obsidian vault before answering.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [obsidian, notes, memory, recall, personal-context]
    related_skills: [obsidian-vault, obsidian-cli, wiki]
---

# Obsidian Memory

## Overview

Treat `~/notes` as the canonical evidence store for Oleksii's personal context. Hermes's compact memory remains useful for stable preferences and routing facts; it is not a replacement for the vault and must not be populated by silently importing every note.

## When to Use

Use this skill before answering questions about Oleksii's preferences, history, decisions, projects, routines, personal knowledge, or facts that may have been recorded in notes. Use it when the user asks to remember, retrieve, or connect information across notes.

Do not invoke it for unrelated general questions or merely because the current conversation mentions a note filename.

## Recall workflow

1. **Resolve the vault.** Run:
   ```bash
   python3 ~/.llm-harness/scripts/skill-path.py path obsidian_vault
   ```
   Verify the resolved directory exists. The configured vault must be the full `~/notes` tree, not only `50 Knowledge/LLM Wiki`.

2. **Use Obsidian-native search first.** When the Obsidian backend is running, use the `obsidian-cli` workflow to search the vault, read candidate notes, and inspect links/backlinks or properties. Search filenames and content; begin with distinctive terms and broaden only when needed.

3. **Use the local fallback when necessary.** If the CLI is unavailable or returns an operational error, use scoped filesystem search/read tools inside the resolved vault. This fallback reads Markdown directly and does not create a second index or invoke QMD.

4. **Read evidence, not snippets alone.** Open the relevant notes, check their headings/frontmatter and dates, and distinguish a current user-stated fact from an old or tentative note. Prefer the smallest set of notes that supports the answer.

5. **Report provenance.** State which note paths support a personal-context answer. If sources conflict, describe the conflict and prefer the newer or explicitly confirmed source; do not silently choose.

## Durable memory workflow

- A request to **remember** something means save a concise, user-confirmed fact in the canonical notes/Wiki location and verify that the resulting note is present and searchable.
- Keep Hermes memory limited to stable, high-value facts that improve future routing or responses. Add provenance when the fact came from a note rather than directly from the user.
- Never silently copy the whole vault, a large note, private attachments, or transient task progress into Hermes memory.
- A note search is evidence for the current answer; it is not permission to promote every discovered statement to durable memory.
- Preserve existing vault conventions, wikilinks, frontmatter, and user-authored text when writing.

## Completion criteria

A recall task is complete only when the answer is grounded in at least one full note or an explicit statement from the current conversation, and the supporting path(s) are known. A memory-write task is complete only when the saved fact exists under `~/notes` and can be found by a subsequent scoped search.

## Pitfalls

1. Searching only the LLM Wiki hub when the question concerns personal context.
2. Treating a stale note as a current preference without checking dates or confirmation.
3. Replacing the holographic memory provider with a vault index merely to enable recall.
4. Writing private or transient note content into compact Hermes memory without an explicit durable-memory reason.
5. Reporting a search result without reading the candidate note that contains it.

## Verification checklist

- [ ] Vault resolution returns the full `~/notes` path.
- [ ] Obsidian-native search was attempted when the backend was available.
- [ ] Filesystem fallback, if used, stayed inside the resolved vault.
- [ ] Candidate notes were read before making personal-context claims.
- [ ] Supporting note paths were retained for the response.
- [ ] Any durable write was verified by a second scoped search.
