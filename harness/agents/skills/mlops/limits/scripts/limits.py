#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from typing import Any

DISPLAY_NAMES = {
    "codex": "Codex",
    "opencodego": "Opencode GO",
    "openai": "OpenAI",
    "gemini": "Gemini",
    "claude": "Claude",
    "openrouter": "OpenRouter",
    "zai": "ZAI",
    "minimax": "MiniMax",
    "kimi": "Kimi",
    "mistral": "Mistral",
    "deepseek": "DeepSeek",
    "alibaba-coding-plan": "Alibaba Coding Plan",
    "vertexai": "Vertex AI",
    "copilot": "Copilot",
    "kilo": "Kilo",
    "ollama": "Ollama",
}

PROVIDER_MAP = {
    "openai-codex": "codex",
    "codex": "codex",
    "openai": "openai",
    "opencode-go": "opencodego",
    "opencodego": "opencodego",
    "opencode": "opencode",
    "google": "gemini",
    "gemini": "gemini",
    "anthropic": "claude",
    "claude": "claude",
    "openrouter": "openrouter",
    "zai": "zai",
    "glm": "zai",
    "minimax": "minimax",
    "kimi": "kimi",
    "moonshot": "kimi",
    "mistral": "mistral",
    "deepseek": "deepseek",
    "qwen": "alibaba-coding-plan",
    "dashscope": "alibaba-coding-plan",
    "alibaba": "alibaba-coding-plan",
    "vertex-ai": "vertexai",
    "vertexai": "vertexai",
    "copilot": "copilot",
    "kilo": "kilo",
}


def map_provider(name: str) -> str:
    key = name.strip().lower().replace("_", "-")
    return PROVIDER_MAP.get(key, key)


def extract_json(stdout: str) -> Any:
    for i, ch in enumerate(stdout):
        if ch in "[{":
            try:
                return json.loads(stdout[i:])
            except Exception:
                pass
    raise ValueError("no JSON found")


def run_usage(timeout: int) -> list[dict[str, Any]]:
    """Fetch all configured providers in one CodexBar JSON request."""
    cmd = ["codexbar", "usage", "--json"]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return [{"provider": "codexbar", "error": f"timeout after {timeout}s"}]
    try:
        payload = extract_json(proc.stdout)
    except Exception as exc:
        return [{"provider": "codexbar", "error": str(exc)}]
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return [{"provider": "codexbar", "error": "empty result"}]
    return [item for item in payload if isinstance(item, dict)]


def parse_resets_at(value: Any) -> datetime.datetime | None:
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def remaining_label(delta: datetime.timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        total_seconds = 0
    days, remainder = divmod(total_seconds, 86400)
    hours = remainder // 3600
    if days >= 1:
        return f"{days}d"
    return f"{hours}h"


def copilot_resets_at(usage: dict[str, Any]) -> datetime.datetime | None:
    """Copilot omits windowMinutes/resetsAt, but the monthly quota resets on the 1st of next month UTC."""
    # If codexbar ever starts including resetsAt, trust it.
    for name in ("primary", "secondary", "tertiary"):
        win = usage.get(name) or {}
        if ts := parse_resets_at(win.get("resetsAt")):
            return ts
    now = datetime.datetime.now(datetime.timezone.utc)
    if now.day == 1:
        return now
    # Move to first day of next month.
    year = now.year + (now.month // 12)
    month = (now.month % 12) + 1
    return datetime.datetime(year, month, 1, tzinfo=datetime.timezone.utc)


def remaining_token(
    win: dict[str, Any], *, default_resets_at: datetime.datetime | None = None
) -> str | None:
    if not win or "usedPercent" not in win:
        return None
    resets_at = parse_resets_at(win.get("resetsAt")) or default_resets_at
    if resets_at is None:
        return None
    try:
        used = float(win["usedPercent"])
    except Exception:
        return None
    remaining = max(0.0, min(100.0, 100.0 - used))
    now = datetime.datetime.now(datetime.timezone.utc)
    return f"{int(remaining + 0.5)}%/{remaining_label(resets_at - now)}"


def format_line(item: dict[str, Any]) -> str | None:
    provider = str(item.get("provider", "unknown"))
    label = DISPLAY_NAMES.get(provider, provider)
    if err := item.get("error"):
        return f"{label}: error ({err})"
    usage = item.get("usage") or {}
    tokens = []
    default_resets_at = copilot_resets_at(usage) if provider == "copilot" else None
    for name in ("primary", "secondary", "tertiary"):
        tok = remaining_token(
            usage.get(name) or {}, default_resets_at=default_resets_at
        )
        if tok:
            tokens.append(tok)
    if not tokens:
        return f"{label}: no limits"
    return f"{label}: {' '.join(tokens)}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", action="append")
    ap.add_argument("--timeout", type=int, default=75)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not shutil.which("codexbar"):
        print("codexbar not found", file=sys.stderr)
        return 127

    results = run_usage(args.timeout)
    if args.provider:
        requested = {map_provider(provider) for provider in args.provider}
        results = [
            item
            for item in results
            if map_provider(str(item.get("provider", ""))) in requested
        ]

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
        return 0

    lines = [line for r in results if (line := format_line(r))]

    print("\n".join(lines))
    return (
        0
        if any(": error (" not in ln and ": no limits" not in ln for ln in lines)
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
