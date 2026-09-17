#!/usr/bin/env python3
"""Cross-platform Aegis installer.

Safe, idempotent, reversible, and stdlib-only. Works on Windows, macOS, and
Linux with Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent
ALL_SKILLS = (
    "aegis-ceo-skills",
    "usage-optimizer",
    "second-brain-context",
    "five-year-old",
)
ENGINE_SRC = ROOT / "aegis-engine"
IGNORED_NAMES = {"__pycache__", ".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def _default_skills_target() -> Path:
    raw = os.environ.get("AEGIS_SKILLS_DIR")
    return Path(raw).expanduser() if raw else Path.home() / ".agents" / "skills"


def _default_engine_target() -> Path:
    raw = os.environ.get("AEGIS_ENGINE_DIR")
    return Path(raw).expanduser() if raw else Path.home() / ".agents" / "aegis"


def _ignored(path: Path) -> bool:
    return any(part in IGNORED_NAMES for part in path.parts) or path.suffix in IGNORED_SUFFIXES


def _files(root: Path) -> List[Path]:
    return sorted(
        p.relative_to(root)
        for p in root.rglob("*")
        if p.is_file() and not _ignored(p.relative_to(root))
    )


def _same_tree(left: Path, right: Path) -> bool:
    if not left.is_dir() or not right.is_dir():
        return False
    left_files = _files(left)
    right_files = _files(right)
    if left_files != right_files:
        return False
    for rel in left_files:
        if (left / rel).read_bytes() != (right / rel).read_bytes():
            return False
    return True


def _backup_path(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = path.with_name(path.name + ".backup-" + stamp)
    if not base.exists():
        return base
    n = 2
    while True:
        candidate = path.with_name(path.name + ".backup-" + stamp + "-" + str(n))
        if not candidate.exists():
            return candidate
        n += 1


def _copy_tree_atomicish(src: Path, dest: Path, previous_backup: Optional[Path]) -> None:
    """Copy src to dest and restore previous_backup if copying fails."""
    try:
        shutil.copytree(str(src), str(dest))
    except Exception:
        if dest.exists():
            shutil.rmtree(str(dest), ignore_errors=True)
        if previous_backup is not None and previous_backup.exists():
            previous_backup.rename(dest)
        raise


def _install_dir(src: Path, dest: Path, keep: bool) -> Tuple[str, Optional[Path]]:
    if dest.exists() and not dest.is_dir():
        raise RuntimeError("{} exists and is not a directory; refusing to touch it".format(dest))

    if dest.is_dir() and _same_tree(src, dest):
        return "unchanged", None

    if dest.is_dir() and keep:
        return "kept", None

    backup = None
    if dest.is_dir():
        backup = _backup_path(dest)
        dest.rename(backup)

    dest.parent.mkdir(parents=True, exist_ok=True)
    _copy_tree_atomicish(src, dest, backup)
    return ("upgraded" if backup else "installed"), backup


def _uninstall_dir(dest: Path) -> Optional[Path]:
    if not dest.exists():
        return None
    if not dest.is_dir():
        raise RuntimeError("{} exists and is not a directory; refusing to touch it".format(dest))
    backup = _backup_path(dest)
    dest.rename(backup)
    return backup


def _validate_sources(skills: Sequence[str]) -> None:
    for skill in skills:
        src = ROOT / skill
        if not (src / "SKILL.md").is_file():
            raise RuntimeError(
                "{} not found next to install.py; use an intact Aegis checkout".format(skill)
            )
    if not (ENGINE_SRC / "aegis.py").is_file():
        raise RuntimeError("aegis-engine is missing from this checkout")


def _smoke_router(target: Path) -> None:
    router = target / "usage-optimizer" / "scripts" / "route_task.py"
    if not router.is_file():
        return
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            str(router),
            "--task",
            "format a README",
            "--kind",
            "formatting",
            "--complexity",
            "low",
            "--risk",
            "low",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError("installed router smoke check failed: {}".format(proc.stderr.strip()))
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("installed router returned invalid JSON") from exc
    if payload.get("route") != "luna":
        raise RuntimeError("installed router returned unexpected route: {!r}".format(payload.get("route")))


def _smoke_engine(engine_target: Path) -> None:
    """Prove the copied mission engine can actually start from its install path."""
    entrypoint = engine_target / "aegis.py"
    if not entrypoint.is_file():
        raise RuntimeError("installed mission engine entrypoint is missing: {}".format(entrypoint))
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, str(entrypoint), "--help"],
        cwd=str(engine_target), capture_output=True, text=True,
        check=False, env=env, timeout=30,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise RuntimeError("installed mission engine smoke check failed: {}".format(detail))
    if "persistent execution layer" not in proc.stdout:
        raise RuntimeError("installed mission engine returned unexpected help output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install, upgrade, or uninstall Aegis safely")
    parser.add_argument("--target", type=Path, default=None, help="skills target directory")
    parser.add_argument("--engine-target", type=Path, default=None, help="mission engine target directory")
    parser.add_argument("--only", action="append", default=[], help="install/uninstall only one named skill; repeatable")
    parser.add_argument("--keep", action="store_true", help="keep differing existing copies instead of upgrading")
    parser.add_argument("--uninstall", action="store_true", help="remove installed copies by moving them to timestamped backups")
    parser.add_argument("--skip-smoke", action="store_true", help="skip installed router and mission-engine smoke verification")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    skills = list(args.only) if args.only else list(ALL_SKILLS)
    unknown = [name for name in skills if name not in ALL_SKILLS]
    if unknown:
        print(
            "error: unknown skill(s): {} (choose from: {})".format(
                ", ".join(unknown), ", ".join(ALL_SKILLS)
            ),
            file=sys.stderr,
        )
        return 2

    target = (args.target or _default_skills_target()).expanduser().resolve()
    engine_target = (args.engine_target or _default_engine_target()).expanduser().resolve()

    try:
        _validate_sources(skills)
        if args.uninstall:
            removed = 0
            for skill in skills:
                dest = target / skill
                backup = _uninstall_dir(dest)
                if backup:
                    removed += 1
                    print("removed {} (backup: {})".format(dest, backup))
            engine_backup = _uninstall_dir(engine_target)
            if engine_backup:
                print("removed {} (backup: {})".format(engine_target, engine_backup))
            if removed == 0 and engine_backup is None:
                print("nothing to uninstall")
            else:
                print("uninstalled {} skill(s); backups are reversible".format(removed))
            return 0

        counts = {"installed": 0, "upgraded": 0, "unchanged": 0, "kept": 0}
        for skill in skills:
            src = ROOT / skill
            dest = target / skill
            state, backup = _install_dir(src, dest, args.keep)
            counts[state] += 1
            if state == "installed":
                print("installed {}".format(dest))
            elif state == "upgraded":
                print("upgraded {} (previous copy: {})".format(dest, backup))
            elif state == "kept":
                print("kept existing {}".format(dest))
            else:
                print("already installed: {}".format(dest))

        engine_state, engine_backup = _install_dir(ENGINE_SRC, engine_target, args.keep)
        if engine_state == "installed":
            print("installed mission engine: {}".format(engine_target))
        elif engine_state == "upgraded":
            print("upgraded mission engine {} (previous copy: {})".format(engine_target, engine_backup))
        elif engine_state == "kept":
            print("kept existing mission engine: {}".format(engine_target))
        else:
            print("engine already installed: {}".format(engine_target))

        if not args.skip_smoke:
            _smoke_router(target)
            if "usage-optimizer" in skills:
                print("verified: installed router answers correctly")
            _smoke_engine(engine_target)
            print("verified: installed mission engine starts correctly")

        print(
            "done: {installed} installed, {upgraded} upgraded, {unchanged} unchanged, {kept} kept (target: {target})".format(
                target=target, **counts
            )
        )
        print("engine: {}".format(engine_target))
        print("next: point your agent host at {}".format(target))
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
