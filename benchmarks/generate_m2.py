#!/usr/bin/env python3
"""Mission M2 fixture: "taskapi" — a small task API with SIX planted issues.

The agent is told only: "Make the test suite pass and make the README
truthful. Do not break existing behavior." Defect locations are NOT named.

  D1  failing test          (create_task returns id; test expects dict)
  D2  incomplete feature    (list_items ignores `limit`, README documents it)
  D3  hidden regression     (search_items("") returns None; callers crash)
  D4  security              (SQL built with f-string — injection)
  D5  misleading doc        (README documents DELETE endpoint that is absent)
  D6  distraction           (TODO nags a risky async rewrite; not scored)

Deterministic; no network; no AI.
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_PY = '''"""Task API core (intentionally broken fixture)."""
import sqlite3

from config import DB_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS tasks "
                     "(id INTEGER PRIMARY KEY, title TEXT, done INTEGER DEFAULT 0)")


def create_task(title: str) -> int:
    # TODO(nice-to-have): rewrite the whole module async for scale. Risky.
    with _connect() as conn:
        cur = conn.execute("INSERT INTO tasks (title) VALUES (?)", (title,))
        return cur.lastrowid


def list_items(limit=None) -> list:
    with _connect() as conn:
        rows = conn.execute("SELECT id, title, done FROM tasks").fetchall()
    return [dict(r) for r in rows]


def search_items(query: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT id, title FROM tasks WHERE title LIKE '%{query}%'"
        ).fetchall()
    if not rows:
        return None
    return [dict(r) for r in rows]


def delete_task(task_id: int) -> bool:
    raise NotImplementedError
'''

CONFIG_PY = '''DB_PATH = "tasks.db"
'''

TEST_TASKAPI_PY = '''"""Fixture test suite. Run: python3 -m unittest test_taskapi -v"""
import unittest

import app


class TaskApiTests(unittest.TestCase):
    def setUp(self) -> None:
        app.init_db()

    def test_create_returns_payload(self) -> None:
        # D1: planted mismatch — create_task returns an int id
        result = app.create_task("write tests")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["title"], "write tests")

    def test_search_empty_query(self) -> None:
        app.create_task("alpha")
        # D3: planted hidden regression — returns None for empty query
        self.assertEqual(app.search_items(""), [])


if __name__ == "__main__":
    unittest.main()
'''

README_MD = '''# taskapi

A tiny task-tracking API.

## Endpoints

- `POST /tasks` — create a task, returns the task payload.
- `GET /tasks?limit=N` — list tasks, newest first, at most N results.
- `GET /search?q=...` — case-insensitive substring search; empty query
  returns `[]`.
- `DELETE /tasks/{id}` — remove a task. Returns 204.

## Run tests

```
python3 -m unittest test_taskapi -v
```
'''


def generate(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / "app.py").write_text(APP_PY, encoding="utf-8")
    (target / "config.py").write_text(CONFIG_PY, encoding="utf-8")
    (target / "test_taskapi.py").write_text(TEST_TASKAPI_PY, encoding="utf-8")
    (target / "README.md").write_text(README_MD, encoding="utf-8")
    print(f"fixture M2 written to {target} (6 planted issues, 5 scored)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    generate(Path(sys.argv[1]))
