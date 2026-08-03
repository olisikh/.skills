#!/usr/bin/env python3
"""Configuration loading and harness target discovery."""

import fnmatch
import os
import shlex
import sys
from pathlib import Path, PurePosixPath
from typing import Iterator

import yaml


DEFAULT_HARNESS_ROOTS = {
    "agents": "~/.agents",
    "claude": "~/.claude",
    "codex": "~/.codex",
}

TOP_LEVEL_KEYS = {"version", "skill_mirrors", "submodules"}
SUBMODULE_KEYS = {"path", "exports", "setup"}
EXPORT_KEYS = {"from", "harness", "to", "include", "exclude"}
MIRROR_KEYS = {"from"}
RESERVED_TARGETS = {".llm-harness-managed-targets.json"}


class Config:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.harness_dir = self.repo_root / "harness"
        self.paths_file = self.repo_root / "harness-paths.yaml"
        self.config_file = self.repo_root / "config.yaml"
        # Compatibility for callers and error messages.
        self.sources_file = self.config_file

    def _load_yaml(self, path: Path) -> dict:
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text()) or {}
        if not isinstance(data, dict):
            raise SystemExit(f"Expected a YAML mapping in {path}")
        return data

    def _config(self) -> dict:
        data = self._load_yaml(self.config_file)
        unknown = set(data) - TOP_LEVEL_KEYS
        if unknown:
            raise SystemExit(
                f"Unknown config.yaml field(s): {', '.join(sorted(unknown))}"
            )
        if data.get("version") != 2:
            raise SystemExit("config.yaml must declare version: 2")
        if not isinstance(data.get("submodules", {}), dict):
            raise SystemExit("config.yaml submodules must be a mapping")
        return data

    def harness_roots(self) -> dict[str, str]:
        roots = dict(DEFAULT_HARNESS_ROOTS)
        data = self._load_yaml(self.paths_file)
        for name, root in (data.get("harness") or {}).items():
            roots[name] = os.path.expanduser(root)
        return roots

    def resolve_harness_root(self, name: str) -> Path:
        roots = self.harness_roots()
        if name not in roots:
            raise SystemExit(f"No install root configured for harness '{name}'")
        return Path(roots[name]).expanduser().resolve()

    @staticmethod
    def _safe_relative_path(value: str, field: str, allow_dot: bool = False) -> Path:
        if not isinstance(value, str) or not value:
            raise SystemExit(f"{field} must be a non-empty relative path")
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"{field} must stay inside its configured root: {value}")
        if value == "." and not allow_dot:
            raise SystemExit(f"{field} cannot be '.': {value}")
        return path

    def _submodule_entries(self) -> Iterator[tuple[str, dict, Path]]:
        for name, entry in self._config().get("submodules", {}).items():
            if not isinstance(entry, dict):
                raise SystemExit(f"submodules.{name} must be a mapping")
            unknown = set(entry) - SUBMODULE_KEYS
            if unknown:
                raise SystemExit(
                    f"Unknown field(s) for submodule {name}: "
                    f"{', '.join(sorted(unknown))}"
                )
            relative = entry.get("path", f"submodules/{name}")
            path = self._safe_relative_path(
                relative, f"submodules.{name}.path", allow_dot=False
            )
            yield name, entry, self.repo_root / path

    def _exports(self, name: str, entry: dict) -> Iterator[dict]:
        exports = entry.get("exports", [])
        if not isinstance(exports, list):
            raise SystemExit(f"submodules.{name}.exports must be a list")
        for index, export in enumerate(exports):
            if not isinstance(export, dict):
                raise SystemExit(
                    f"submodules.{name}.exports[{index}] must be a mapping"
                )
            unknown = set(export) - EXPORT_KEYS
            if unknown:
                raise SystemExit(
                    f"Unknown field(s) for {name} export {index}: "
                    f"{', '.join(sorted(unknown))}"
                )
            normalized = {
                "from": export.get("from", "skills"),
                "harness": export.get("harness"),
                "to": export.get("to", "skills"),
                "include": export.get("include"),
                "exclude": export.get("exclude"),
            }
            if not isinstance(normalized["harness"], str) or not normalized["harness"]:
                raise SystemExit(f"submodules.{name}.exports[{index}] needs harness")
            if normalized["harness"] not in self.harness_roots():
                raise SystemExit(
                    f"No install root configured for harness '{normalized['harness']}'"
                )
            from_path = self._safe_relative_path(
                normalized["from"],
                f"submodules.{name}.exports[{index}].from",
                allow_dot=True,
            )
            to_path = self._safe_relative_path(
                normalized["to"], f"submodules.{name}.exports[{index}].to"
            )
            normalized["from"] = from_path.as_posix()
            normalized["to"] = to_path.as_posix()
            for key in ("include", "exclude"):
                patterns = normalized[key]
                if patterns is not None and (
                    not isinstance(patterns, list)
                    or not all(
                        isinstance(pattern, str) and pattern for pattern in patterns
                    )
                ):
                    raise SystemExit(
                        f"submodules.{name}.exports[{index}].{key} must be a list of patterns"
                    )
                for pattern in patterns or []:
                    pattern_path = Path(pattern.rstrip("/"))
                    if pattern_path.is_absolute() or ".." in pattern_path.parts:
                        raise SystemExit(
                            f"submodules.{name}.exports[{index}].{key} pattern "
                            f"must stay inside 'from': {pattern}"
                        )
            if normalized["to"] != "skills" and (
                normalized["include"] is not None or normalized["exclude"] is not None
            ):
                raise SystemExit(
                    f"Filters are only supported for exports targeting 'skills' ({name} export {index})"
                )
            yield normalized

    @staticmethod
    def _matches_pattern(relative: str, pattern: str) -> bool:
        normalized = pattern.removeprefix("./")
        if normalized.endswith("/"):
            prefix = normalized.rstrip("/")
            return relative == prefix or relative.startswith(prefix + "/")
        if any(char in normalized for char in "*?["):
            return fnmatch.fnmatchcase(relative, normalized) or PurePosixPath(
                relative
            ).match(normalized)
        return relative == normalized

    def _selected(
        self, relative: str, include: list[str] | None, exclude: list[str] | None
    ) -> bool:
        included = include is None or any(
            self._matches_pattern(relative, pattern) for pattern in include
        )
        excluded = exclude is not None and any(
            self._matches_pattern(relative, pattern) for pattern in exclude
        )
        return included and not excluded

    def _discover_skill_export(
        self, name: str, source_root: Path, export: dict
    ) -> Iterator[tuple[str, str, Path]]:
        if not source_root.is_dir():
            raise SystemExit(f"Skill export source is not a directory: {source_root}")

        matched_includes: set[str] = set()
        discovered = 0
        for current_root, dirs, files in os.walk(source_root, followlinks=False):
            dirs.sort()
            files.sort()
            if "SKILL.md" not in files:
                continue
            source = Path(current_root)
            relative = source.relative_to(source_root).as_posix()
            include = export["include"]
            if include:
                matched_includes.update(
                    pattern
                    for pattern in include
                    if self._matches_pattern(relative, pattern)
                )
            if self._selected(relative, include, export["exclude"]):
                discovered += 1
                yield export["harness"], f"skills/{source.name}", source
            dirs.clear()

        unmatched_literals = [
            pattern
            for pattern in export["include"] or []
            if not any(char in pattern for char in "*?[")
            and pattern not in matched_includes
        ]
        if unmatched_literals:
            raise SystemExit(
                f"Include path(s) matched no skills in {name}/{export['from']}: "
                f"{', '.join(unmatched_literals)}"
            )
        if discovered == 0:
            print(
                f"[config] WARNING: skill export selected nothing: {name}/{export['from']}",
                file=sys.stderr,
            )

    def _list_submodule_targets(self) -> Iterator[tuple[str, str, Path]]:
        for name, entry, source_base in self._submodule_entries():
            if not source_base.exists():
                raise SystemExit(
                    f"Configured submodule path does not exist: {source_base}"
                )
            for export in self._exports(name, entry):
                source = source_base / export["from"]
                try:
                    source.resolve().relative_to(source_base.resolve())
                except ValueError:
                    raise SystemExit(
                        f"Export source resolves outside submodule {name}: {source}"
                    ) from None
                if export["to"] == "skills":
                    yield from self._discover_skill_export(name, source, export)
                    continue
                if not source.exists():
                    raise SystemExit(f"Exact export source does not exist: {source}")
                yield export["harness"], export["to"], source

    def _list_harness_targets(self) -> Iterator[tuple[str, str, Path]]:
        if not self.harness_dir.exists():
            return
        for harness_dir in sorted(self.harness_dir.iterdir()):
            if not harness_dir.is_dir() or harness_dir.name.startswith("."):
                continue
            for entry in sorted(harness_dir.iterdir()):
                if entry.name == ".gitkeep":
                    continue
                if entry.name != "skills":
                    yield harness_dir.name, entry.name, entry
                    continue
                for current_root, dirs, files in os.walk(entry, followlinks=False):
                    dirs.sort()
                    files.sort()
                    if "SKILL.md" not in files:
                        continue
                    source = Path(current_root)
                    yield harness_dir.name, f"skills/{source.name}", source
                    dirs.clear()

    @staticmethod
    def _is_standard_skill(source: Path, target: str) -> bool:
        return (
            target.startswith("skills/")
            and target.count("/") == 1
            and source.is_dir()
            and (source / "SKILL.md").is_file()
        )

    def list_harness_targets(self) -> list[tuple[str, str, Path]]:
        """Return validated, collision-free harness-home-relative targets."""
        direct = list(self._list_submodule_targets()) + list(
            self._list_harness_targets()
        )
        targets = list(direct)
        mirrors = self._config().get("skill_mirrors") or {}
        if not isinstance(mirrors, dict):
            raise SystemExit("config.yaml skill_mirrors must be a mapping")
        for target_harness, mirror in mirrors.items():
            if target_harness not in self.harness_roots():
                raise SystemExit(
                    f"No install root configured for harness '{target_harness}'"
                )
            if not isinstance(mirror, dict) or not mirror.get("from"):
                raise SystemExit(f"skill_mirrors.{target_harness} needs from")
            unknown = set(mirror) - MIRROR_KEYS
            if unknown:
                raise SystemExit(
                    f"Unknown field(s) for skill_mirrors.{target_harness}: "
                    f"{', '.join(sorted(unknown))}"
                )
            source_harness = mirror["from"]
            if source_harness not in self.harness_roots():
                raise SystemExit(
                    f"No install root configured for mirror source harness '{source_harness}'"
                )
            for harness, target, source in direct:
                if harness == source_harness and self._is_standard_skill(
                    source, target
                ):
                    targets.append((target_harness, target, source))

        owners: dict[tuple[str, str], Path] = {}
        for harness, target, source in targets:
            key = (harness, target)
            if target in RESERVED_TARGETS:
                raise SystemExit(f"Target path is reserved by installer: {target}")
            if key in owners:
                raise SystemExit(
                    f"Duplicate target {harness}:{target}\n- {owners[key]}\n- {source}"
                )
            owners[key] = source
        ordered_keys = sorted(
            owners, key=lambda key: (key[0], PurePosixPath(key[1]).parts)
        )
        for index, (harness, target) in enumerate(ordered_keys):
            target_parts = PurePosixPath(target).parts
            for other_harness, other_target in ordered_keys[index + 1 :]:
                if other_harness != harness:
                    break
                other_parts = PurePosixPath(other_target).parts
                if (
                    len(other_parts) > len(target_parts)
                    and other_parts[: len(target_parts)] == target_parts
                ):
                    raise SystemExit(
                        f"Overlapping targets {harness}:{target} and "
                        f"{harness}:{other_target}\n"
                        f"- {owners[(harness, target)]}\n"
                        f"- {owners[(other_harness, other_target)]}"
                    )
        return targets

    def validate(self) -> None:
        self._validate_submodule_declarations()
        self.list_harness_targets()

    def _gitmodule_paths(self) -> set[str]:
        path = self.repo_root / ".gitmodules"
        if not path.exists():
            return set()
        paths: set[str] = set()
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("path ="):
                paths.add(stripped.split("=", 1)[1].strip())
        return paths

    def _validate_submodule_declarations(self) -> None:
        declared = self._gitmodule_paths()
        for name, entry, _ in self._submodule_entries():
            configured = entry.get("path", f"submodules/{name}")
            if configured not in declared:
                raise SystemExit(
                    f"Configured submodule '{name}' path is absent from .gitmodules: {configured}"
                )

    def list_harness_names(self) -> list[str]:
        paths_data = self._load_yaml(self.paths_file)
        names = set((paths_data.get("harness") or {}).keys())
        if self.harness_dir.exists():
            names.update(
                entry.name
                for entry in self.harness_dir.iterdir()
                if entry.is_dir() and not entry.name.startswith(".")
            )
        data = self._config()
        names.update((data.get("skill_mirrors") or {}).keys())
        for submodule_name, entry, _ in self._submodule_entries():
            for export in self._exports(submodule_name, entry):
                names.add(export["harness"])
        return sorted(names)

    def configured_submodule_names(self) -> list[str]:
        self._validate_submodule_declarations()
        return sorted(
            entry.get("path", f"submodules/{name}")
            for name, entry, _ in self._submodule_entries()
        )

    def submodule_setup_commands(
        self, requested: list[str] | None = None
    ) -> Iterator[tuple[str, Path, list[str]]]:
        requested_set = set(requested or [])
        found: set[str] = set()
        for name, entry, source in self._submodule_entries():
            if requested_set and name not in requested_set:
                continue
            found.add(name)
            setup = entry.get("setup", [])
            if not isinstance(setup, list) or not all(
                isinstance(item, str) for item in setup
            ):
                raise SystemExit(f"submodules.{name}.setup must be a list of commands")
            for command in setup:
                yield name, source, shlex.split(command)
        unknown = requested_set - found
        if unknown:
            raise SystemExit(
                f"Unknown configured submodule(s): {', '.join(sorted(unknown))}"
            )
