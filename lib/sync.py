#!/usr/bin/env python3
"""Install and uninstall synchronization logic."""

import json
import os
import sys
from pathlib import Path
from typing import Callable

from lib.config import Config


MANIFEST_NAME = ".llm-harness-managed-targets.json"


def log(msg: str) -> None:
    print(f"[install] {msg}")


def warn(msg: str) -> None:
    print(f"[install] WARNING: {msg}", file=sys.stderr)


def resolve_path(path: Path | str) -> Path:
    return Path(path).resolve()


def sync_target(
    source_abs: Path,
    target_abs: Path,
    log_fn: Callable[[str], None],
    managed_root: Path | None = None,
) -> bool:
    expected = resolve_path(source_abs)

    if target_abs.is_symlink():
        resolved = resolve_path(target_abs)
        if resolved == expected:
            log_fn(f"Link already exists at {target_abs}")
            return True
        if managed_root is not None:
            try:
                resolved.relative_to(resolve_path(managed_root))
            except ValueError:
                pass
            else:
                target_abs.unlink()
                target_abs.symlink_to(source_abs)
                log_fn(f"Repaired {target_abs} -> {source_abs}")
                return True
        warn(f"Skipping existing symlink at {target_abs} (points elsewhere)")
        return False

    if target_abs.exists():
        warn(f"Skipping existing path at {target_abs}")
        return False

    target_abs.parent.mkdir(parents=True, exist_ok=True)
    target_abs.symlink_to(source_abs)
    log_fn(f"Linked {target_abs} -> {source_abs}")
    return True


def _target_stays_in_root(target: Path, target_root: Path) -> bool:
    try:
        target.parent.resolve().relative_to(target_root.resolve())
    except ValueError:
        return False
    return True


def _manifest_path(target_root: Path) -> Path:
    return target_root / MANIFEST_NAME


def _read_managed_targets(target_root: Path) -> set[str] | None:
    manifest = _manifest_path(target_root)
    if not manifest.exists():
        return None
    try:
        data = json.loads(manifest.read_text())
    except (json.JSONDecodeError, OSError) as error:
        raise SystemExit(f"Invalid managed-target manifest {manifest}: {error}")
    if data.get("version") != 1 or not isinstance(data.get("targets"), list):
        raise SystemExit(f"Invalid managed-target manifest: {manifest}")
    targets = data["targets"]
    if not all(
        isinstance(target, str)
        and target
        and not Path(target).is_absolute()
        and ".." not in Path(target).parts
        for target in targets
    ):
        raise SystemExit(f"Invalid managed target path in: {manifest}")
    return set(targets)


def _write_managed_targets(target_root: Path, targets: set[str]) -> None:
    manifest = _manifest_path(target_root)
    rendered = json.dumps({"version": 1, "targets": sorted(targets)}, indent=2) + "\n"
    temporary = manifest.with_suffix(".tmp")
    temporary.write_text(rendered)
    temporary.replace(manifest)


def prune_empty_parent_dirs(path: Path, stop_dir: Path) -> None:
    current = path.parent
    stop = stop_dir.resolve()
    while str(current).startswith(str(stop) + os.sep):
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _prune_skill_parents(path: Path, target_root: Path) -> None:
    relative = path.relative_to(target_root)
    if relative.parts and relative.parts[0] == "skills":
        prune_empty_parent_dirs(path, target_root / "skills")


def list_managed_symlinks(target_root: Path, repo_root: Path) -> list[Path]:
    managed: list[Path] = []
    if not target_root.exists():
        return managed

    repo_root_resolved = repo_root.resolve()
    for current_root, dirs, files in os.walk(target_root, followlinks=False):
        dirs.sort()
        files.sort()
        for name in dirs + files:
            path = Path(current_root) / name
            if not path.is_symlink():
                continue
            try:
                resolved = path.resolve()
            except OSError:
                continue
            try:
                resolved.relative_to(repo_root_resolved)
            except ValueError:
                continue
            managed.append(path)
    return managed


def sync_harness(config: Config, harness_name: str) -> None:
    target_root = config.resolve_harness_root(harness_name)

    if not target_root.exists():
        log(f"Skipping [{harness_name}]: {target_root} does not exist")
        return

    log(f"[{harness_name}] -> {target_root}")

    desired_sources: dict[Path, Path] = {}

    for harness, rel, source in config.list_harness_targets():
        if harness != harness_name:
            continue
        target = target_root / rel
        desired_sources[target] = source

    previous = _read_managed_targets(target_root)
    if previous is None:
        # One-time migration from the pre-manifest installer. Skills were the
        # only recursively managed namespace in that version. Top-level links
        # were managed only when they pointed into this harness source tree.
        previous_paths = set(
            list_managed_symlinks(target_root / "skills", config.repo_root)
        )
        harness_source = config.harness_dir / harness_name
        for path in target_root.iterdir():
            if not path.is_symlink():
                continue
            try:
                path.resolve().relative_to(harness_source.resolve())
            except ValueError:
                continue
            previous_paths.add(path)
    else:
        previous_paths = {target_root / relative for relative in previous}

    for target, source in desired_sources.items():
        if not _target_stays_in_root(target, target_root):
            warn(
                f"Skipping target outside harness root through symlinked parent: {target}"
            )
            continue
        sync_target(source, target, log, managed_root=config.repo_root)

    desired_target_set = set(desired_sources)
    for existing in previous_paths:
        if existing in desired_target_set:
            continue
        if existing.is_symlink():
            if not _target_stays_in_root(existing, target_root):
                warn(f"Skipping stale target outside harness root: {existing}")
                continue
            try:
                existing.resolve().relative_to(config.repo_root.resolve())
            except ValueError:
                continue
            existing.unlink()
            log(f"Removed stale {existing}")
            _prune_skill_parents(existing, target_root)

    _write_managed_targets(
        target_root,
        {target.relative_to(target_root).as_posix() for target in desired_target_set},
    )


def uninstall_harness(config: Config, harness_name: str) -> None:
    target_root = config.resolve_harness_root(harness_name)

    if not target_root.exists():
        print(f"[uninstall] Skipping [{harness_name}]: {target_root} does not exist")
        return

    print(f"[uninstall] [{harness_name}]")

    previous = _read_managed_targets(target_root)
    if previous is None:
        managed = list_managed_symlinks(target_root / "skills", config.repo_root)
    else:
        managed = [target_root / relative for relative in previous]
    for existing in managed:
        if not existing.is_symlink():
            continue
        if not _target_stays_in_root(existing, target_root):
            warn(f"Skipping uninstall target outside harness root: {existing}")
            continue
        try:
            existing.resolve().relative_to(config.repo_root.resolve())
        except ValueError:
            continue
        existing.unlink()
        print(f"[uninstall] Removed {existing}")
        _prune_skill_parents(existing, target_root)
    manifest = _manifest_path(target_root)
    if manifest.exists():
        manifest.unlink()
