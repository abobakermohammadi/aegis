#!/usr/bin/env python3
"""Machine-readable Aegis mission report for CI and agent automation.

Prints one JSON document to stdout. Exit codes:
  0 report produced and requested conditions hold
  1 report produced but a requested condition is not satisfied
  2 invalid/missing Aegis state

Stdlib-only, Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine import core, gitinfo
from engine import state as state_mod

SCHEMA_VERSION = 1


def _payload(project: Path) -> dict:
    st, notes = state_mod.load(project)
    gates = core.verify_mission(project, st)
    doctor = core.doctor(project)

    open_defects = [
        {"id": d["id"], "title": d["title"], "severity": d.get("severity")}
        for d in st.get("defects", [])
        if d.get("status") == "open"
    ]
    unresolved_blockers = [
        {
            "id": b["id"],
            "kind": b.get("kind", ""),
            "title": b.get("title", ""),
            "blocks": b.get("blocks", ""),
        }
        for b in st.get("blockers", [])
        if not b.get("resolved")
    ]
    completion_blockers = [
        b for b in unresolved_blockers if b.get("kind") in ("decision", "credentials")
    ]

    m = st["mission"]
    return {
        "schema_version": SCHEMA_VERSION,
        "mission": {
            "id": m["id"],
            "goal": m["goal"],
            "phase": m["phase"],
            "release": m.get("release", ""),
        },
        "ready_to_complete": bool(gates["can_complete"] and not completion_blockers),
        "gates": {
            "required_pass": gates["required_pass"],
            "required_total": gates["required_total"],
            "can_complete": gates["can_complete"],
            "criteria": gates["criteria"],
        },
        "health": {
            "healthy": doctor["healthy"],
            "findings": doctor.get("findings", []),
        },
        "work": {
            "open_defects": open_defects,
            "unresolved_blockers": unresolved_blockers,
            "completion_blockers": completion_blockers,
            "checkpoint_count": len(st.get("checkpoints", [])),
            "regression_count": len(st.get("regressions", [])),
        },
        "git": {
            "head": gitinfo.head_commit(project),
            "dirty_files": gitinfo.dirty_files(project),
        },
        "deploy": st.get("deploy", {}),
        "notes": notes,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aegis-ci",
        description="Emit a stable JSON report for CI and agent automation.",
    )
    p.add_argument("--project", default=".", help="project directory (default: current directory)")
    p.add_argument("--pretty", action="store_true", help="indent JSON for humans")
    p.add_argument(
        "--require-complete",
        action="store_true",
        help="exit 1 unless all required gates pass and completion blockers are resolved",
    )
    p.add_argument(
        "--require-healthy",
        action="store_true",
        help="exit 1 when Aegis doctor reports an unhealthy mission",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project = Path(args.project).expanduser()
    try:
        payload = _payload(project)
    except state_mod.StateError as exc:
        print(json.dumps({"schema_version": SCHEMA_VERSION, "error": str(exc)}, sort_keys=True))
        return 2

    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    if args.require_complete and not payload["ready_to_complete"]:
        return 1
    if args.require_healthy and not payload["health"]["healthy"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
