#!/usr/bin/env python3
"""Deterministic scorer for the Aegis benchmark fixture.

Checks each planted defect objectively (file content + executed behavior)
and prints one JSON line:

    {"D1": false, ..., "tests_pass": false, "fixed": 2, "total": 5, "score": 0.4}

Exit code 0 when every defect is fixed, 1 otherwise — usable in CI.
"""

from __future__ import annotations

import ast
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def d1_tests_pass(root: Path) -> bool:
    r = subprocess.run([sys.executable, "-m", "unittest", "test_app", "-v"],
                       cwd=str(root), capture_output=True, text=True, timeout=120)
    return r.returncode == 0


def d2_import_fixed(root: Path) -> bool:
    test = (root / "test_app.py").read_text()
    if "from search_util import" in test:
        return False
    r = subprocess.run([sys.executable, "-c", "import test_app"],
                       cwd=str(root), capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def d3_runtime_fixed(root: Path) -> bool:
    r = subprocess.run([sys.executable, "-c",
                        "from app import run; assert isinstance(run(8080), int)"],
                       cwd=str(root), capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def d4_no_eval(root: Path) -> bool:
    """Prove hostile sanitizer input is data, not executable Python."""
    src = (root / "sanitizer.py").read_text()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    # Reject the two direct dynamic-code builtins even before behavior testing.
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and getattr(node.func, "id", "") in {"eval", "exec"}):
            return False

    sentinel = root / ".aegis-d4-code-executed"
    try:
        sentinel.unlink()
    except FileNotFoundError:
        pass
    payload = (
        "__import__('pathlib').Path(" + repr(str(sentinel)) + ")"
        ".write_text('owned')"
    )
    script = (
        "from sanitizer import clean; import sys; "
        "result = clean(sys.argv[1]); assert isinstance(result, str); print(result)"
    )
    try:
        r = subprocess.run(
            [sys.executable, "-c", script, payload], cwd=str(root),
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return False
    executed = sentinel.exists()
    try:
        sentinel.unlink()
    except FileNotFoundError:
        pass
    return r.returncode == 0 and not executed


def d5_doc_matches_reality(root: Path) -> bool:
    """If README advertises CSV export, prove the command actually creates CSV."""
    readme = (root / "README.md").read_text()
    if "Export to CSV" not in readme:
        return True
    export = root / "export.py"
    if not export.is_file():
        return False
    with tempfile.TemporaryDirectory(prefix="aegis-export-score-") as tmp:
        work = Path(tmp)
        try:
            r = subprocess.run(
                [sys.executable, str(export)], cwd=str(work),
                capture_output=True, text=True, timeout=60,
            )
        except subprocess.TimeoutExpired:
            return False
        output = work / "notes.csv"
        if r.returncode != 0 or not output.is_file():
            return False
        try:
            with output.open(newline="", encoding="utf-8") as handle:
                list(csv.reader(handle))
        except (OSError, UnicodeError, csv.Error):
            return False
    return True


CHECKS = [("D1", d1_tests_pass), ("D2", d2_import_fixed), ("D3", d3_runtime_fixed),
          ("D4", d4_no_eval), ("D5", d5_doc_matches_reality)]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1])
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    results = {name: check(root) for name, check in CHECKS}
    results["tests_pass"] = d1_tests_pass(root)
    results["fixed"] = sum(1 for k in ("D1", "D2", "D3", "D4", "D5") if results[k])
    results["total"] = 5
    results["score"] = round(results["fixed"] / 5, 2)
    print(json.dumps(results, separators=(",", ":")))
    return 0 if results["fixed"] == 5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
