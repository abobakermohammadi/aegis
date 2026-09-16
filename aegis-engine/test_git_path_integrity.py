"""Adversarial path-integrity tests for git-aware evidence freshness."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))

from engine import core, gitinfo, state as state_mod  # noqa: E402


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        capture_output=True, check=True,
    )


class GitPathIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="aegis-git-paths-")
        self.project = Path(self._tmp.name) / "project"
        self.project.mkdir()
        git(self.project, "init", "-q")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def commit_all(self, message: str) -> None:
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", message)

    def _state_with_guard(self, guarded_path: str) -> dict:
        st = state_mod.empty_state("path integrity", "")
        st["criteria"].append({
            "id": "C1", "text": "guarded behavior passes", "required": True,
            "evidence": [], "blocked_reason": None,
        })
        entry, _ = core.add_evidence(
            self.project, st, "C1", "test",
            command=sys.executable + " -c \"print('ok')\"", manual_note=None,
        )
        entry["files"] = [guarded_path]
        return st

    def test_unicode_guarded_path_becomes_stale_after_commit(self) -> None:
        path = "café-安全.py"
        (self.project / path).write_text("value = 1\n", encoding="utf-8")
        self.commit_all("initial")
        st = self._state_with_guard(path)
        self.assertEqual(core.gate_status(self.project, st, st["criteria"][0])[0], "pass")

        (self.project / path).write_text("value = 2\n", encoding="utf-8")
        self.commit_all("change unicode path")

        self.assertIn(path, gitinfo.changed_since(self.project, st["evidence"][0]["commit"]))
        self.assertEqual(core.gate_status(self.project, st, st["criteria"][0])[0], "stale")

    def test_dirty_files_preserves_whitespace_unicode_and_both_rename_sides(self) -> None:
        old = "old café name.py"
        new = "new 安全 name.py"
        (self.project / old).write_text("x = 1\n", encoding="utf-8")
        self.commit_all("initial")
        (self.project / old).rename(self.project / new)

        dirty = gitinfo.dirty_files(self.project)
        self.assertIn(old, dirty)
        self.assertIn(new, dirty)

    def test_changed_since_preserves_both_rename_sides(self) -> None:
        old = "guard old.py"
        new = "guard 新.py"
        (self.project / old).write_text("x = 1\n", encoding="utf-8")
        self.commit_all("initial")
        before = gitinfo.head_commit(self.project)
        (self.project / old).rename(self.project / new)
        self.commit_all("rename")

        changed = gitinfo.changed_since(self.project, before)
        self.assertIsNotNone(changed)
        self.assertIn(old, changed)
        self.assertIn(new, changed)


if __name__ == "__main__":
    unittest.main()
