#!/usr/bin/env python3
"""Deterministic helpers for the Obsidian-first LLM Wiki v2 format.

Markdown and frontmatter are authoritative. The registry and Maps are derived
views. This module deliberately uses only the Python standard library so it can
run from Hermes, OpenClaw hooks, or a portable agent checkout.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import posixpath
import re
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 2
TODAY = os.environ.get("LLM_WIKI_TODAY", dt.date.today().isoformat())[:10]
ROOT_DIRS = (
    "00 Inbox",
    "10 Sources",
    "20 Knowledge",
    "30 Projects",
    "40 Outputs",
    "80 Maps",
    "90 System",
    "99 Archive",
)
SOURCE_DIRS = ("Articles", "Repositories", "Papers", "Notes", "Data")
CONTENT_DIRS = ("00 Inbox", "10 Sources", "20 Knowledge", "30 Projects", "40 Outputs")
KIND_BY_WIKI_DIR = {
    "concepts": "concept",
    "topics": "topic",
    "references": "reference",
    "theses": "thesis",
}
SOURCE_TYPE_LABELS = {
    "articles": "Articles",
    "repos": "Repositories",
    "papers": "Papers",
    "notes": "Notes",
    "data": "Data",
}
DOMAIN_LABELS = {
    "dotfiles": "Dotfiles",
    "hermes": "Hermes",
    "openclaw": "OpenClaw",
    "obsidian": "Obsidian",
    "plane": "Plane",
    "tailscale": "Tailscale",
    "vikunja": "Vikunja",
    "telegram-car-index-bot": "Telegram Car Index Bot",
}
META_ORDER = (
    "id",
    "title",
    "summary",
    "kind",
    "domains",
    "tags",
    "status",
    "aliases",
    "created",
    "updated",
    "source_refs",
    "confidence",
    "source_type",
    "source_url",
    "ingested",
    "legacy_path",
    "legacy_type",
    "legacy_source_refs",
    "external_refs",
)


@dataclass
class Record:
    old_path: str
    old_file: Path
    topic: str
    title: str
    kind: str
    source_type: str | None
    metadata: dict[str, Any]
    body: str
    target_rel: str = ""
    stable_id: str = ""


def scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value.lower() in {"null", "none", "~"}:
        return None
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.startswith("[") and value.endswith("]"):
        return [scalar(part) for part in split_list(value[1:-1]) if part.strip()]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def split_list(value: str) -> list[str]:
    result: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for char in value:
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            current.append(char)
        elif char == "," and quote is None:
            result.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    result.append("".join(current).strip())
    return result


def split_document(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    block = text[4:end]
    body = text[end + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    result: dict[str, Any] = {}
    current: str | None = None
    for line in block.splitlines():
        if line.startswith("  - ") and current:
            existing = result.setdefault(current, [])
            if not isinstance(existing, list):
                existing = []
                result[current] = existing
            existing.append(scalar(line[4:]))
            continue
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if not key:
            continue
        current = key
        result[key] = scalar(value)
    return result, body


def as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def yaml_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(yaml_value(item) if re.fullmatch(r"[A-Za-z0-9_./:@+-]+", str(item)) else json.dumps(str(item), ensure_ascii=False) for item in value) + "]"
    text = str(value)
    if re.fullmatch(r"[A-Za-z0-9_./:@+-]+", text):
        return text
    return json.dumps(text, ensure_ascii=False)


def dump_document(metadata: dict[str, Any], body: str) -> str:
    keys = [key for key in META_ORDER if key in metadata]
    keys.extend(sorted(key for key in metadata if key not in keys))
    lines = ["---"]
    for key in keys:
        value = metadata[key]
        if isinstance(value, list):
            lines.append(f"{key}: {yaml_value(value)}")
        else:
            lines.append(f"{key}: {yaml_value(value)}")
    lines.extend(["---", ""])
    return "\n".join(lines) + body.lstrip("\n")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return normalized or "note"


def safe_filename(value: str, fallback: str) -> str:
    value = re.sub(r"[\\/:?*\"<>|]", "-", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    if not value:
        value = fallback
    return value[:150] + ".md"


def label_for_domain(domain: str) -> str:
    return DOMAIN_LABELS.get(domain, domain.replace("-", " ").title())


def domains_for_topic(topic: str, existing: Any) -> list[str]:
    values = [slugify(value) for value in as_list(existing)]
    if values:
        return list(dict.fromkeys(values))
    if topic == "obsidian-hermes":
        return ["obsidian", "hermes"]
    return [slugify(topic)]


def tags_for(topic: str, kind: str, existing: Any) -> list[str]:
    values = [slugify(value) for value in as_list(existing)]
    values.extend([slugify(topic), kind])
    return list(dict.fromkeys(value for value in values if value))


def read_text(path: Path) -> tuple[dict[str, Any], str]:
    return split_document(path.read_text(encoding="utf-8"))


def write_text(path: Path, metadata: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_document(metadata, body), encoding="utf-8")


def old_kind(relative: Path, metadata: dict[str, Any]) -> tuple[str, str | None]:
    parts = relative.parts
    if len(parts) >= 4 and parts[0] == "topics":
        layer = parts[2]
        if layer == "raw":
            return "source", parts[3]
        if layer == "wiki":
            return KIND_BY_WIKI_DIR.get(parts[3], "knowledge"), None
        if layer == "output":
            return "output", None
        if layer == "inbox":
            return "inbox", None
    legacy_type = str(metadata.get("type", "")).strip().lower()
    if legacy_type in {"source", "article", "paper", "repo", "note", "data"}:
        return "source", None
    if legacy_type in {"output", "artifact"}:
        return "output", None
    return "knowledge", None


def discover(old_hub: Path) -> list[Record]:
    records: list[Record] = []
    topics = old_hub / "topics"
    if not topics.is_dir():
        raise SystemExit(f"legacy hub has no topics directory: {topics}")
    for path in sorted(topics.rglob("*.md")):
        relative = path.relative_to(old_hub)
        if path.name == "_index.md":
            continue
        if path.name in {"config.md", "schema.md", "log.md"}:
            continue
        metadata, body = read_text(path)
        topic = relative.parts[1] if len(relative.parts) > 1 else "general"
        kind, source_type = old_kind(relative, metadata)
        title = str(metadata.get("title") or path.stem.replace("-", " ").replace("_", " ")).strip()
        seed = str(metadata.get("id") or f"{topic}-{path.stem}")
        stable_id = slugify(seed)
        if not stable_id.startswith(slugify(topic) + "-") and not metadata.get("id"):
            stable_id = slugify(f"{topic}-{path.stem}")
        records.append(Record(str(relative), path, topic, title, kind, source_type, metadata, body, stable_id=stable_id))
    used_ids: dict[str, str] = {}
    for record in records:
        prior = used_ids.get(record.stable_id)
        if prior and prior != record.old_path:
            digest = hashlib.sha256(record.old_path.encode("utf-8")).hexdigest()[:8]
            record.stable_id = f"{record.stable_id}-{digest}"
        used_ids[record.stable_id] = record.old_path
    used_targets: dict[str, str] = {}
    for record in records:
        if record.kind == "source":
            folder = SOURCE_TYPE_LABELS.get(record.source_type or "notes", "Notes")
            parent = Path("10 Sources") / folder
        elif record.kind == "output":
            parent = Path("40 Outputs")
        elif record.kind == "inbox":
            parent = Path("00 Inbox")
        elif record.kind == "project":
            parent = Path("30 Projects")
        else:
            parent = Path("20 Knowledge")
        filename = safe_filename(record.title, record.stable_id)
        candidate = (parent / filename).as_posix()
        if candidate in used_targets:
            filename = safe_filename(f"{record.title} — {record.stable_id}", record.stable_id)
            candidate = (parent / filename).as_posix()
        used_targets[candidate] = record.old_path
        record.target_rel = candidate
    return records


def old_path_candidates(current: str, reference: str) -> Iterable[str]:
    value = reference.strip().strip("<>").split("#", 1)[0]
    if not value or value.startswith(("http://", "https://", "mailto:", "#")):
        return []
    current_path = Path(current)
    base = current_path.parent
    candidate = Path(value)
    candidates: list[str] = []
    for path in (base / candidate, Path("topics") / current_path.parts[1] / candidate, candidate):
        normalized = posixpath.normpath(path.as_posix())
        if normalized.startswith("../"):
            continue
        candidates.append(normalized)
    return candidates


def resolve_reference(current: str, reference: str, by_path: dict[str, Record], by_name: dict[str, list[Record]]) -> Record | None:
    for candidate in old_path_candidates(current, reference):
        if candidate in by_path:
            return by_path[candidate]
    stem = Path(reference.split("#", 1)[0]).stem
    matches = by_name.get(stem.lower(), [])
    return matches[0] if len(matches) == 1 else None


def rewrite_body(body: str, current: str, by_path: dict[str, Record], by_name: dict[str, list[Record]], by_key: dict[str, Record]) -> str:
    def wiki_replacement(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        label = (match.group(2) or "").strip()
        record = by_key.get(target.lower()) or by_key.get(slugify(target))
        if record:
            return f"[[{record.title}]]"
        return f"[[{label or target}]]"

    body = re.sub(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]", wiki_replacement, body)

    def markdown_replacement(match: re.Match[str]) -> str:
        label, target = match.group(1), match.group(2).strip()
        record = resolve_reference(current, target, by_path, by_name)
        if record:
            return f"[[{record.title}]]"
        # Keep the human label while removing an obsolete tree-relative path.
        return f"[[{label}]]"

    return re.sub(r"\[([^\]]+)\]\(([^)]+\.md(?:#[^)]*)?)\)", markdown_replacement, body)


def normalized_source_refs(record: Record, by_path: dict[str, Record], by_name: dict[str, list[Record]]) -> tuple[list[str], list[str], list[str]]:
    resolved: list[str] = []
    unresolved: list[str] = []
    external: list[str] = []
    for reference in as_list(record.metadata.get("source_refs", record.metadata.get("sources", []))):
        target = resolve_reference(record.old_path, reference, by_path, by_name)
        if target:
            resolved.append(target.stable_id)
        elif not reference.strip().endswith(".md"):
            external.append(reference)
        else:
            unresolved.append(reference)
    return list(dict.fromkeys(resolved)), list(dict.fromkeys(unresolved)), list(dict.fromkeys(external))


def make_metadata(record: Record, source_refs: list[str], unresolved: list[str], external: list[str]) -> dict[str, Any]:
    old = record.metadata
    metadata: dict[str, Any] = {
        "id": record.stable_id,
        "title": record.title,
        "summary": str(old.get("summary", "")).strip(),
        "kind": record.kind,
        "domains": domains_for_topic(record.topic, old.get("domains")),
        "tags": tags_for(record.topic, record.kind, old.get("tags")),
        "status": str(old.get("status", "active")),
        "aliases": as_list(old.get("aliases")),
        "created": str(old.get("created", TODAY)),
        "updated": str(old.get("updated", old.get("created", TODAY))),
        "source_refs": source_refs,
        "confidence": str(old.get("confidence", "medium")),
        "legacy_path": record.old_path,
    }
    if record.kind == "source":
        metadata["source_type"] = record.source_type or str(old.get("type", "note"))
    for key in ("source_url", "ingested"):
        if key in old:
            metadata[key] = old[key]
    if old.get("type") and old.get("type") != record.kind:
        metadata["legacy_type"] = old["type"]
    if unresolved:
        metadata["legacy_source_refs"] = unresolved
    if external:
        metadata["external_refs"] = external
    if record.title not in metadata["aliases"] and record.old_file.stem.replace("-", " ") != record.title:
        metadata["aliases"].append(record.old_file.stem.replace("-", " "))
    return metadata


def write_schema(root: Path) -> None:
    schema = """---
id: llm-wiki-v2-schema
title: LLM Wiki v2 Schema
summary: Authoritative metadata and placement contract for the Obsidian-first LLM Wiki.
kind: system
domains: [llm-wiki]
tags: [schema, v2, metadata]
status: active
aliases: [Wiki v2 schema]
created: 2026-08-10
updated: 2026-08-10
source_refs: []
confidence: high
---

# LLM Wiki v2 Schema

Markdown and YAML frontmatter are authoritative. Folders, Maps, the registry,
and indexes are derived navigation views.

## Active root layout

- `00 Inbox/` — unprocessed human or agent captures.
- `10 Sources/` — immutable evidence, grouped only by source medium.
- `20 Knowledge/` — flat durable knowledge; use `kind` for concept, topic,
  reference, thesis, decision, or other semantic roles.
- `30 Projects/` — active delivery work and project briefs.
- `40 Outputs/` — generated reports and artifacts.
- `80 Maps/` — readable domain and status navigation pages.
- `90 System/` — rebuildable registry, logs, schema, migration maps, and
  redacted session state.
- `99 Archive/` — compatibility preservation excluded from normal recall.

## Required note fields

```yaml
id: stable-lowercase-identity
title: Human-readable title
kind: source | concept | topic | reference | thesis | decision | project | output | inbox
domains: [hermes, obsidian]
tags: [memory, backend]
status: active | draft | superseded | archived
aliases: [alternate title]
created: YYYY-MM-DD
updated: YYYY-MM-DD
source_refs: [stable-source-id]
confidence: high | medium | low
external_refs: [conversation-or-local-external-reference]
```

`id` is stable across moves. `domains` and `tags` are many-to-many metadata;
no note is duplicated merely because it belongs to multiple domains.

## Linking

Use canonical Obsidian wikilinks such as `[[Hermes Obsidian Backend]]`. The
resolver uses `id`, title, aliases, and the registry. Relative Markdown links
are accepted during migration but are not required in new notes.

## Safety

Sources are immutable after capture. The registry and Maps may be rebuilt. The
legacy path map preserves lookup from the old topic/category layout. Archived
material is not used for normal answers unless explicitly requested.
"""
    target = root / "90 System" / "schema.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(schema, encoding="utf-8")


def copy_legacy_guides(old_hub: Path, root: Path) -> None:
    destination = root / "99 Archive" / "Legacy Guides"
    for topic in sorted((old_hub / "topics").iterdir()):
        if not topic.is_dir():
            continue
        for name in ("config.md", "schema.md"):
            source = topic / name
            if source.is_file():
                target = destination / topic.name / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        log = topic / "log.md"
        if log.is_file():
            target = root / "90 System" / "logs" / f"{topic.name}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(log, target)
    hub_log = old_hub / "log.md"
    if hub_log.is_file():
        target = root / "90 System" / "logs" / "hub.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(hub_log, target)
    for name in (".sessions", ".maintenance"):
        source = old_hub / name
        if source.exists():
            target = root / "90 System" / name
            if not target.exists():
                shutil.copytree(source, target)


def build_registry(root: Path) -> dict[str, Any]:
    entries: dict[str, Any] = {}
    duplicates: list[str] = []
    for directory in CONTENT_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            metadata, _body = read_text(path)
            if path.name == "_index.md" or not metadata.get("id"):
                continue
            stable_id = str(metadata["id"])
            if stable_id in entries:
                duplicates.append(stable_id)
                continue
            entries[stable_id] = {
                "path": path.relative_to(root).as_posix(),
                "title": metadata.get("title", path.stem),
                "kind": metadata.get("kind", "knowledge"),
                "domains": as_list(metadata.get("domains")),
                "tags": as_list(metadata.get("tags")),
                "status": metadata.get("status", "active"),
                "aliases": as_list(metadata.get("aliases")),
                "source_refs": as_list(metadata.get("source_refs")),
                "updated": metadata.get("updated", ""),
            }
    if duplicates:
        raise SystemExit(f"duplicate registry ids: {', '.join(sorted(set(duplicates)))}")
    registry: dict[str, Any] = {"_meta": {"schema_version": SCHEMA_VERSION, "generated": TODAY}}
    registry.update(dict(sorted(entries.items())))
    target = root / "90 System" / "registry.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return registry


def link_for(root: Path, entry: dict[str, Any]) -> str:
    path = entry["path"][:-3] if entry["path"].endswith(".md") else entry["path"]
    return f"[[{path}|{entry['title']}]]"


def write_map(root: Path, map_id: str, title: str, domains: list[str], body: str) -> None:
    metadata = {
        "id": map_id,
        "title": title,
        "summary": f"Generated navigation map for {title}.",
        "kind": "map",
        "domains": domains,
        "tags": ["map", *domains],
        "status": "active",
        "aliases": [],
        "created": TODAY,
        "updated": TODAY,
        "source_refs": [],
        "confidence": "high",
    }
    write_text(root / "80 Maps" / f"{title}.md", metadata, body)


def build_maps(root: Path, registry: dict[str, Any] | None = None) -> None:
    registry = registry or build_registry(root)
    entries = [entry for key, entry in registry.items() if not key.startswith("_")]
    by_domain: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        for domain in entry.get("domains", []):
            by_domain.setdefault(domain, []).append(entry)
    maps_dir = root / "80 Maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    for domain, domain_entries in sorted(by_domain.items()):
        label = label_for_domain(domain)
        lines = [f"# {label}", "", f"Navigation map for the **{label}** domain.", "", "## Knowledge", ""]
        groups = [("knowledge", {"concept", "topic", "reference", "thesis", "decision", "system", "knowledge"}), ("projects", {"project"}), ("outputs", {"output"}), ("sources", {"source"})]
        for heading, kinds in groups:
            selected = sorted((item for item in domain_entries if item.get("kind") in kinds), key=lambda item: (item.get("title", "").lower(), item.get("path", "")))
            if not selected:
                continue
            if heading != "knowledge":
                lines.extend([f"## {heading.title()}", ""])
            for item in selected:
                lines.append(f"- {link_for(root, item)} — {item.get('kind', 'note')}; updated {item.get('updated', '')}")
            lines.append("")
        write_map(root, f"map-{slugify(domain)}", label, [domain], "\n".join(lines).rstrip() + "\n")

    decisions = sorted((entry for entry in entries if entry.get("kind") == "decision"), key=lambda item: item.get("updated", ""), reverse=True)
    lines = ["# Active Decisions", "", "Decisions are durable choices with explicit provenance.", ""]
    lines.extend(f"- {link_for(root, item)} — updated {item.get('updated', '')}" for item in decisions) or lines.append("_No decisions recorded yet._")
    write_map(root, "map-active-decisions", "Active Decisions", [], "\n".join(lines) + "\n")

    recent = sorted(entries, key=lambda item: item.get("updated", ""), reverse=True)[:50]
    lines = ["# Recently Updated", "", "Generated from note metadata; use the registry for exact lookup.", ""]
    lines.extend(f"- {link_for(root, item)} — {item.get('kind', 'note')}; {item.get('updated', '')}" for item in recent) or lines.append("_No notes yet._")
    write_map(root, "map-recently-updated", "Recently Updated", [], "\n".join(lines) + "\n")

    home_metadata = {
        "id": "llm-wiki-home",
        "title": "LLM Wiki Home",
        "summary": "Human entry point for the Obsidian-first LLM Wiki v2.",
        "kind": "map",
        "domains": ["llm-wiki"],
        "tags": ["home", "map", "navigation"],
        "status": "active",
        "aliases": ["Wiki Home"],
        "created": TODAY,
        "updated": TODAY,
        "source_refs": [],
        "confidence": "high",
    }
    home_lines = [
        "# LLM Wiki",
        "",
        "> **Home → Map → note.** Folders describe operational role; metadata describes meaning.",
        "",
        "## Navigate",
        "",
        "- [[80 Maps/Recently Updated|Recently Updated]]",
        "- [[80 Maps/Active Decisions|Active Decisions]]",
    ]
    for domain in sorted(by_domain):
        label = label_for_domain(domain)
        home_lines.append(f"- [[80 Maps/{label}|{label}]]")
    home_lines.extend([
        "",
        "## Layers",
        "",
        "- `10 Sources/` — immutable evidence.",
        "- `20 Knowledge/` — flat durable understanding.",
        "- `30 Projects/` — active delivery work.",
        "- `40 Outputs/` — generated artifacts.",
        "- `90 System/registry.json` — rebuildable machine index.",
        "- `99 Archive/` — preserved legacy material, excluded from normal recall.",
        "",
        "## Agent contract",
        "",
        "Use `~/.config/llm-wiki/config.json` to resolve this root. Read the Home page,",
        "then resolve stable IDs, titles, aliases, or tags through the registry before",
        "reading the smallest set of exact notes needed for an answer.",
        "",
    ])
    write_text(root / "Home.md", home_metadata, "\n".join(home_lines))


def write_legacy_map(root: Path, records: list[Record]) -> None:
    mapping: dict[str, Any] = {"_meta": {"schema_version": SCHEMA_VERSION, "generated": TODAY, "source": "pre-v2 hub/topics layout"}}
    for record in records:
        mapping[record.old_path] = {"path": record.target_rel, "id": record.stable_id, "title": record.title, "kind": record.kind}
    mapping["hub/_index.md"] = {"path": "Home.md", "id": "llm-wiki-home", "title": "LLM Wiki Home", "kind": "map"}
    (root / "90 System").mkdir(parents=True, exist_ok=True)
    (root / "90 System" / "legacy-path-map.json").write_text(json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def migrate(old_hub: Path, root: Path) -> dict[str, Any]:
    old_hub = old_hub.resolve()
    root = root.resolve()
    if old_hub == root:
        raise SystemExit("legacy hub and v2 root must be different paths")
    records = discover(old_hub)
    root.mkdir(parents=True, exist_ok=True)
    for directory in ROOT_DIRS:
        (root / directory).mkdir(parents=True, exist_ok=True)
    by_path = {record.old_path: record for record in records}
    by_name: dict[str, list[Record]] = {}
    by_key: dict[str, Record] = {}
    for record in records:
        by_name.setdefault(record.old_file.stem.lower(), []).append(record)
        for key in (record.stable_id, record.title.lower(), slugify(record.title), record.old_file.stem.lower()):
            by_key.setdefault(key, record)
    for record in records:
        source_refs, unresolved, external = normalized_source_refs(record, by_path, by_name)
        metadata = make_metadata(record, source_refs, unresolved, external)
        body = rewrite_body(record.body, record.old_path, by_path, by_name, by_key)
        write_text(root / record.target_rel, metadata, body)
    copy_legacy_guides(old_hub, root)
    write_schema(root)
    write_legacy_map(root, records)
    registry = build_registry(root)
    build_maps(root, registry)
    return {"records": len(records), "registry_entries": len(registry) - 1, "root": str(root), "legacy_hub": str(old_hub)}


def archive_legacy(old_hub: Path, root: Path) -> Path:
    old_hub = old_hub.resolve()
    root = root.resolve()
    archive = root / "99 Archive" / "Legacy Hub"
    if not old_hub.exists():
        raise SystemExit(f"legacy hub does not exist: {old_hub}")
    if archive.exists():
        raise SystemExit(f"archive already exists: {archive}")
    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old_hub), str(archive))
    return archive


def load_registry(root: Path) -> dict[str, Any]:
    path = root / "90 System" / "registry.json"
    if not path.is_file():
        return build_registry(root)
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for directory in ROOT_DIRS:
        if not (root / directory).is_dir():
            errors.append(f"missing root directory: {directory}/")
    ids: dict[str, str] = {}
    for directory in CONTENT_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            metadata, body = read_text(path)
            if not metadata:
                errors.append(f"missing frontmatter: {path.relative_to(root)}")
                continue
            required = {"id", "title", "kind", "domains", "tags", "status", "created", "updated", "source_refs"}
            missing = sorted(required - set(metadata))
            if missing:
                errors.append(f"{path.relative_to(root)}: missing {', '.join(missing)}")
            stable_id = str(metadata.get("id", ""))
            if stable_id in ids:
                errors.append(f"duplicate id {stable_id}: {ids[stable_id]} and {path.relative_to(root)}")
            elif stable_id:
                ids[stable_id] = path.relative_to(root).as_posix()
            if re.search(r"\]\([^)]*(?:hub/topics|/raw/|/wiki/|/output/)", body):
                warnings.append(f"legacy markdown path remains: {path.relative_to(root)}")
    registry = load_registry(root)
    for stable_id, entry in registry.items():
        if stable_id.startswith("_"):
            continue
        target = root / entry.get("path", "")
        if not target.is_file():
            errors.append(f"registry target missing for {stable_id}: {entry.get('path')}")
        if stable_id not in ids:
            warnings.append(f"registry entry is not in active content: {stable_id}")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "notes": len(ids), "registry_entries": len([key for key in registry if not key.startswith("_")])}


def resolve(root: Path, query: str) -> dict[str, Any]:
    registry = load_registry(root)
    needle = query.strip().lower()
    exact: list[tuple[str, dict[str, Any]]] = []
    fuzzy: list[tuple[str, dict[str, Any]]] = []
    for stable_id, entry in registry.items():
        if stable_id.startswith("_"):
            continue
        fields = [stable_id, str(entry.get("title", "")), *as_list(entry.get("aliases")), *as_list(entry.get("tags")), *as_list(entry.get("domains"))]
        lower = [field.lower() for field in fields]
        if needle in lower:
            exact.append((stable_id, entry))
        elif any(needle in field for field in lower):
            fuzzy.append((stable_id, entry))
    matches = exact or fuzzy
    return {"query": query, "matches": [{"id": stable_id, **entry} for stable_id, entry in matches[:20]]}


def root_from_config(config: Path | None = None) -> Path:
    config = config or Path.home() / ".config" / "llm-wiki" / "config.json"
    if not config.is_file():
        raise SystemExit(f"missing wiki config: {config}")
    data = json.loads(config.read_text(encoding="utf-8"))
    value = data.get("hub_path") if isinstance(data, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"wiki config has no hub_path: {config}")
    if value == "~":
        return Path.home().resolve()
    if value.startswith("~/"):
        return (Path.home() / value[2:]).resolve()
    return Path(value).expanduser().resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM Wiki v2 deterministic tooling")
    parser.add_argument("--root", type=Path, help="v2 Wiki root; defaults to config hub_path")
    sub = parser.add_subparsers(dest="command", required=True)
    migrate_parser = sub.add_parser("migrate", help="copy legacy hub content into v2")
    migrate_parser.add_argument("--legacy-hub", type=Path, required=True)
    sub.add_parser("registry", help="rebuild 90 System/registry.json")
    sub.add_parser("maps", help="rebuild Home.md and 80 Maps")
    validate_parser = sub.add_parser("validate", help="validate v2 structure and registry")
    validate_parser.add_argument("--strict", action="store_true")
    archive_parser = sub.add_parser("archive-legacy", help="move the old hub into 99 Archive")
    archive_parser.add_argument("--legacy-hub", type=Path, required=True)
    resolve_parser = sub.add_parser("resolve", help="resolve an id, title, alias, tag, or domain")
    resolve_parser.add_argument("query")
    args = parser.parse_args()
    root = (args.root or root_from_config()).expanduser().resolve()
    if args.command == "migrate":
        print(json.dumps(migrate(args.legacy_hub.expanduser(), root), indent=2))
        return 0
    if args.command == "registry":
        print(json.dumps({"entries": len(build_registry(root)) - 1, "root": str(root)}, indent=2))
        return 0
    if args.command == "maps":
        build_maps(root)
        print(json.dumps({"maps": len(list((root / "80 Maps").glob("*.md"))), "root": str(root)}, indent=2))
        return 0
    if args.command == "validate":
        report = validate(root)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["ok"] or not args.strict else 2
    if args.command == "archive-legacy":
        print(json.dumps({"archive": str(archive_legacy(args.legacy_hub.expanduser(), root))}, indent=2))
        return 0
    if args.command == "resolve":
        print(json.dumps(resolve(root, args.query), indent=2, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
