#!/usr/bin/env python3
"""Objective scorer for benchmark mission M2 (taskapi).

Checks outcomes, not claims. Prints one JSON line and exits 0 only at 5/5.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(root: Path, code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", code], cwd=str(root),
                          capture_output=True, text=True, timeout=120)


def d1_suite_green_and_payload(root: Path) -> bool:
    r = subprocess.run([sys.executable, "-m", "unittest", "test_taskapi"],
                       cwd=str(root), capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return False
    # create_task must return a dict payload (test asserts it, but verify
    # independently so a weakened test cannot hide a regression).
    r = _run(root, "import app; r = app.create_task('x'); "
             "assert isinstance(r, dict), r")
    return r.returncode == 0


def d2_limit_honored(root: Path) -> bool:
    with tempfile.TemporaryDirectory() as td:
        code = (
            f"import app; app.DB_PATH = r'{td}/t.db';"
            "app.init_db();"
            "[app.create_task(f't{i}') for i in range(7)];"
            "assert len(app.list_items(limit=3)) == 3, app.list_items(limit=3);"
            "assert len(app.list_items()) == 7"
        )
        return _run(root, code).returncode == 0


def d3_empty_query_returns_list(root: Path) -> bool:
    with tempfile.TemporaryDirectory() as td:
        code = (f"import app; app.DB_PATH = r'{td}/t.db'; app.init_db(); "
                "app.create_task('zz'); "
                "r = app.search_items(''); assert r == [], r")
        return _run(root, code).returncode == 0


def d4_no_sql_injection(root: Path) -> bool:
    src = (root / "app.py").read_text()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        # Direct f-string SQL construction is always unsafe here.
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "execute":
            if node.args and isinstance(node.args[0], ast.JoinedStr):
                return False
    # Behavioral oracle: an injection string must be treated as a literal
    # search term. Returning every row is a security failure, even if no
    # exception is raised and the return type looks correct.
    with tempfile.TemporaryDirectory() as td:
        code = (
            "import app;"
            f"app.DB_PATH = r'{td}/t.db';"
            "app.init_db(); app.create_task('normal'); app.create_task('other');"
            "rows = app.search_items(\"' OR 1=1 --\");"
            "assert rows == [], rows"
        )
        return _run(root, code).returncode == 0


def d5_doc_matches_impl(root: Path) -> bool:
    readme = (root / "README.md").read_text()
    impl = (root / "app.py").read_text()
    # DELETE documented -> prove it removes the created row; alternatively the
    # unsupported endpoint may be removed from the docs.
    if "DELETE /tasks" in readme:
        if "def delete_task" not in impl:
            return False
        with tempfile.TemporaryDirectory() as td:
            code = (
                "import app;"
                f"app.DB_PATH = r'{td}/t.db';"
                "app.init_db(); created = app.create_task('delete-me');"
                "tid = created['id'] if isinstance(created, dict) else created;"
                "assert app.delete_task(tid) is True;"
                "assert all(row.get('id') != tid for row in app.list_items()), app.list_items()"
            )
            return _run(root, code).returncode == 0
    return True


CHECKS = [("D1", d1_suite_green_and_payload), ("D2", d2_limit_honored),
          ("D3", d3_empty_query_returns_list), ("D4", d4_no_sql_injection),
          ("D5", d5_doc_matches_impl)]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1])
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    results = {name: check(root) for name, check in CHECKS}
    suite = subprocess.run([sys.executable, "-m", "unittest", "test_taskapi"],
                           cwd=str(root), capture_output=True, timeout=120)
    results["tests_pass"] = suite.returncode == 0
    results["fixed"] = sum(1 for k, _ in CHECKS if results[k])
    results["total"] = len(CHECKS)
    results["score"] = round(results["fixed"] / len(CHECKS), 2)
    print(json.dumps(results, separators=(",", ":")))
    return 0 if results["fixed"] == len(CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
