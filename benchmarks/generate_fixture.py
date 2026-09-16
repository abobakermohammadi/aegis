#!/usr/bin/env python3
"""Generate a deterministic broken-project fixture for Aegis benchmarks.

The fixture is a small "web notes app" with five planted defects:

  D1  failing unit test      (test asserts wrong expected value)
  D2  broken import          (module renamed, caller not updated)
  D3  runtime crash          (config port typo: str where int required)
  D4  security defect        (eval() on user input)
  D5  stale documentation    (README claims a feature that does not exist)

Usage:  python3 generate_fixture.py <target-dir>
The generator is deterministic: same output every run, no network, no AI.
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_PY = '''"""Notes app (intentionally broken fixture)."""
from store import load_notes, save_notes
from sanitizer import clean


def add_note(text: str) -> list[str]:
    notes = load_notes()
    notes.append(clean(text))
    save_notes(notes)
    return notes


def render(port: str) -> str:
    # D3: config passes a string; server expects an int port
    return f"notes-server listening on {port}"


def run(port: int) -> str:
    return render(port)
'''

SANITIZER_PY = '''"""Input sanitization."""


def clean(text: str) -> str:
    # D4: security defect — evaluates input instead of sanitizing it
    return str(eval(text))
'''

STORE_PY = '''"""Note persistence."""
import json
from pathlib import Path

PATH = Path("notes.json")


def load_notes() -> list[str]:
    if PATH.exists():
        return json.loads(PATH.read_text())
    return []


def save_notes(notes: list[str]) -> None:
    PATH.write_text(json.dumps(notes))
'''

SEARCH_PY = '''"""Full-text search over notes."""


def search(notes: list[str], query: str) -> list[str]:
    q = query.lower()
    return [n for n in notes if q in n.lower()]
'''

TEST_APP_PY = '''"""Fixture test suite. Run: python3 -m unittest test_app -v"""
import tempfile
import unittest
from pathlib import Path

import store
from app import add_note, render, run
# D2: broken import — search.py exists but the project imports search_util
from search_util import search


class NotesTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.write(b"[]")
        tmp.close()
        store.PATH = Path(tmp.name)

    def tearDown(self) -> None:
        if store.PATH.exists():
            store.PATH.unlink()

    def test_add_and_search(self) -> None:
        notes = add_note("hello world")
        self.assertEqual(search(notes, "world"), ["hello world"])

    def test_render(self) -> None:
        self.assertIn("listening", render("8080"))

    def test_run_type(self) -> None:
        # D1: failing test — the app returns the raw string, test expects int
        self.assertIsInstance(run(8080), int)


if __name__ == "__main__":
    unittest.main()
'''

README_MD = '''# Notes App

A tiny notes service.

## Features

- Add notes (sanitized).
- Search notes.
- **Export to CSV** — run `python3 export.py` to produce `notes.csv`.

## Run tests

```
python3 -m unittest test_app -v
```
'''

INIT_PY = ""

DEFECTS = ["D1 failing unit test", "D2 broken import", "D3 runtime crash",
           "D4 eval() security defect", "D5 stale README feature claim"]


def generate(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / "app.py").write_text(APP_PY, encoding="utf-8")
    (target / "sanitizer.py").write_text(SANITIZER_PY, encoding="utf-8")
    (target / "store.py").write_text(STORE_PY, encoding="utf-8")
    (target / "search.py").write_text(SEARCH_PY, encoding="utf-8")
    (target / "test_app.py").write_text(TEST_APP_PY, encoding="utf-8")
    (target / "README.md").write_text(README_MD, encoding="utf-8")
    print(f"fixture written to {target} with {len(DEFECTS)} planted defects:")
    for d in DEFECTS:
        print(f"  - {d}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    generate(Path(sys.argv[1]))
