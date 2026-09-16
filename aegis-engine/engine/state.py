"""Mission state: versioned schema, atomic storage, validation, migration.

The state file `<project>/aegis/mission.json` is the single authoritative
source of truth for an Aegis mission. Writes are atomic (tmp + rename), keep a
`.bak` of the last good version, and reject stale concurrent writers rather
than silently losing another process's update.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
STATE_DIR_NAME = "aegis"
STATE_FILE_NAME = "mission.json"
MAX_STATE_BYTES = 5 * 1024 * 1024
LOCK_DIR_NAME = ".mission.lock"
LOCK_WAIT_SECONDS = 5.0
LOCK_STALE_SECONDS = 30.0

KINDS_BLOCKER = ("credentials", "decision", "failure", "inconvenience")
PHASES = ("discover", "design", "build", "verify", "ship", "done")


class StateError(Exception):
    """Raised when mission state cannot be safely loaded or saved."""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix: str, existing) -> str:
    numbers = [int(e["id"][len(prefix):]) for e in existing
               if e["id"].startswith(prefix) and e["id"][len(prefix):].isdigit()]
    return f"{prefix}{max(numbers, default=0) + 1}"


def empty_state(goal: str, why: str = "", mission_id: str | None = None) -> dict:
    return {
        "schema": SCHEMA_VERSION,
        "_revision": 0,
        "mission": {
            "id": mission_id or ("m-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")),
            "goal": goal,
            "why": why,
            "created_at": now_iso(),
            "constraints": [],
            "non_goals": [],
            "phase": "discover",
            "release": "",
        },
        "criteria": [],
        "workstreams": [],
        "defects": [],
        "blockers": [],
        "evidence": [],
        "decisions": [],
        "regressions": [],
        "checkpoints": [],
        "deploy": {"target": "", "state": "unknown", "url": "", "last_checked_at": ""},
        "next_hint": "",
    }


def validate(state: dict) -> list[str]:
    """Return a list of problems (empty list = structurally valid)."""
    problems: list[str] = []
    if not isinstance(state, dict):
        return ["state is not an object"]
    schema = state.get("schema")
    if schema is None:
        problems.append("missing schema version")
    elif not isinstance(schema, int) or schema < 1:
        problems.append(f"invalid schema version: {schema!r}")
    revision = state.get("_revision", 0)
    if not isinstance(revision, int) or revision < 0:
        problems.append(f"invalid state revision: {revision!r}")
    mission = state.get("mission")
    if not isinstance(mission, dict):
        problems.append("missing mission object")
    else:
        if not str(mission.get("goal", "")).strip():
            problems.append("mission.goal is empty")
        if mission.get("phase") not in PHASES:
            problems.append(f"mission.phase invalid: {mission.get('phase')!r}")
    ids: set[str] = set()

    def check_id(entity: dict, prefix: str) -> None:
        eid = entity.get("id")
        if not isinstance(eid, str) or not eid.startswith(prefix):
            problems.append(f"bad id {eid!r} (expected prefix {prefix})")
        elif eid in ids:
            problems.append(f"duplicate id {eid}")
        ids.add(eid)

    for c in state.get("criteria", []):
        check_id(c, "C")
        if not str(c.get("text", "")).strip():
            problems.append(f"{c.get('id')}: empty criterion text")
    for w in state.get("workstreams", []):
        check_id(w, "W")
        if w.get("impact") not in (1, 2, 3):
            problems.append(f"{w.get('id')}: impact must be 1-3")
        if w.get("effort") not in (1, 2, 3):
            problems.append(f"{w.get('id')}: effort must be 1-3")
    for d in state.get("defects", []):
        check_id(d, "D")
    for b in state.get("blockers", []):
        check_id(b, "B")
        if b.get("kind") not in KINDS_BLOCKER:
            problems.append(f"{b.get('id')}: blocker kind invalid: {b.get('kind')!r}")
    for e in state.get("evidence", []):
        check_id(e, "E")
        if e.get("exit") is not None and not isinstance(e.get("exit"), int):
            problems.append(f"{e.get('id')}: evidence exit must be integer or null")
    for dec in state.get("decisions", []):
        check_id(dec, "DEC")
    for r in state.get("regressions", []):
        check_id(r, "R")

    evidence_ids = {e.get("id") for e in state.get("evidence", [])}
    for c in state.get("criteria", []):
        for ev in c.get("evidence", []):
            if ev not in evidence_ids:
                problems.append(f"{c.get('id')}: references missing evidence {ev}")
    return problems


def migrate(state: dict) -> tuple[dict, list[str]]:
    """Migrate older schemas to the current one. Returns (state, notes)."""
    notes: list[str] = []
    schema = state.get("schema", 0)
    if not isinstance(schema, int):
        raise StateError(f"schema version is not an integer: {schema!r}")
    if schema > SCHEMA_VERSION:
        raise StateError(
            f"state schema {schema} is newer than this engine (supports <= {SCHEMA_VERSION}); "
            "upgrade Aegis instead of downgrading state"
        )
    if schema < 1:
        base = empty_state(str(state.get("mission", {}).get("goal", "imported mission")))
        merged = {**base, **state}
        merged["schema"] = SCHEMA_VERSION
        base_keys = set(base)
        for key in base_keys:
            merged.setdefault(key, base[key])
        notes.append("migrated schema 0 -> 1 (defaults filled)")
        state = merged
    state.setdefault("_revision", 0)
    return state, notes


def state_dir(project: Path) -> Path:
    return project / STATE_DIR_NAME


def state_path(project: Path) -> Path:
    return state_dir(project) / STATE_FILE_NAME


def load(project: Path, migrate_on_load: bool = True) -> tuple[dict, list[str]]:
    """Load and validate state. Returns (state, notes)."""
    path = state_path(project)
    if path.is_symlink():
        raise StateError(f"{path} is a symlink; refusing to read it (possible attack)")
    if not path.exists():
        raise StateError(f"no mission state at {path}; run 'aegis init' first")
    size = path.stat().st_size
    if size > MAX_STATE_BYTES:
        raise StateError(
            f"state file is {size} bytes (limit {MAX_STATE_BYTES}); "
            "inspect it manually, then archive or trim aegis/"
        )
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StateError(f"cannot read {path}: {exc}") from exc
    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        bak = path.with_suffix(".json.bak")
        raise StateError(
            f"state file is corrupt ({exc.msg} at line {exc.lineno}). "
            f"Recover with: aegis doctor   (a backup may exist at {bak})"
        ) from exc
    if migrate_on_load:
        state, notes = migrate(state)
    else:
        notes = []
    problems = validate(state)
    if problems:
        raise StateError("state validation failed:\n  - " + "\n  - ".join(problems))
    return state, notes


def _acquire_write_lock(sdir: Path) -> Path:
    """Acquire a small cross-platform lock directory for compare-and-swap."""
    lock = sdir / LOCK_DIR_NAME
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    while True:
        if lock.is_symlink():
            raise StateError(f"{lock} is a symlink; refusing write lock (possible attack)")
        try:
            os.mkdir(lock)
            return lock
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                age = 0
            if age > LOCK_STALE_SECONDS and lock.is_dir() and not lock.is_symlink():
                try:
                    os.rmdir(lock)
                    continue
                except OSError:
                    pass
            if time.monotonic() >= deadline:
                raise StateError("timed out waiting for another Aegis state writer; reload and retry")
            time.sleep(0.05)
        except OSError as exc:
            raise StateError(f"cannot acquire state write lock {lock}: {exc}") from exc


def _disk_revision(path: Path) -> int:
    """Read the current revision while holding the writer lock."""
    if not path.exists():
        return 0
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(
            f"cannot safely compare current mission state before write: {exc}; "
            "run 'aegis doctor' instead of overwriting it"
        ) from exc
    revision = raw.get("_revision", 0)
    if not isinstance(revision, int) or revision < 0:
        raise StateError(f"current mission state has invalid revision {revision!r}")
    return revision


def save(project: Path, state: dict) -> None:
    """Atomically persist state and reject stale concurrent writers.

    Each loaded state carries an internal monotonic ``_revision``. The write
    lock makes the disk-revision comparison and replacement one critical
    section. A process that loaded revision N cannot overwrite revision N+1;
    it must reload, preventing silent lost updates.
    """
    sdir = state_dir(project)
    if sdir.is_symlink():
        raise StateError(f"{sdir} is a symlink; refusing to write (possible attack)")
    sdir.mkdir(parents=True, exist_ok=True)
    lock = _acquire_write_lock(sdir)
    tmp_name = None
    try:
        path = state_path(project)
        if path.is_symlink():
            raise StateError(f"{path} is a symlink; refusing to overwrite (possible attack)")
        expected = state.get("_revision", 0)
        if not isinstance(expected, int) or expected < 0:
            raise StateError(f"invalid in-memory state revision {expected!r}")
        current = _disk_revision(path)
        if path.exists() and current != expected:
            raise StateError(
                f"mission state changed concurrently (loaded revision {expected}, "
                f"current revision {current}); reload and retry instead of overwriting newer work"
            )
        state["_revision"] = expected + 1
        problems = validate(state)
        if problems:
            state["_revision"] = expected
            raise StateError("refusing to save invalid state:\n  - " + "\n  - ".join(problems))
        payload = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if len(payload.encode("utf-8")) > MAX_STATE_BYTES:
            state["_revision"] = expected
            raise StateError("state exceeds size limit; archive old checkpoints/evidence first")
        fd, tmp_name = tempfile.mkstemp(dir=sdir, prefix=".mission-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            shutil.copyfile(path, path.with_suffix(".json.bak"))
        os.replace(tmp_name, path)
        tmp_name = None
    except OSError as exc:
        state["_revision"] = max(0, state.get("_revision", 1) - 1)
        raise StateError(f"cannot write {state_path(project)}: {exc}") from exc
    except BaseException:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        raise
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        try:
            os.rmdir(lock)
        except OSError:
            pass
