"""Deterministic lost-update and writer-lock regression tests."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))

from engine import state as state_mod  # noqa: E402


class StateConcurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="aegis-state-cas-")
        self.project = Path(self._tmp.name) / "project"
        self.project.mkdir()
        state_mod.save(self.project, state_mod.empty_state("g"))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_stale_snapshot_cannot_overwrite_newer_state(self) -> None:
        first, _ = state_mod.load(self.project)
        stale, _ = state_mod.load(self.project)
        self.assertEqual(first["_revision"], stale["_revision"])

        first["workstreams"].append({
            "id": "W1", "title": "first writer", "impact": 2, "effort": 2,
            "status": "open", "depends_on": [], "notes": "",
        })
        state_mod.save(self.project, first)

        stale["workstreams"].append({
            "id": "W1", "title": "stale writer", "impact": 2, "effort": 2,
            "status": "open", "depends_on": [], "notes": "",
        })
        with self.assertRaisesRegex(state_mod.StateError, "changed concurrently"):
            state_mod.save(self.project, stale)

        current, _ = state_mod.load(self.project)
        self.assertEqual([w["title"] for w in current["workstreams"]], ["first writer"])
        self.assertGreater(current["_revision"], stale["_revision"])

    def test_sequential_saves_advance_revision(self) -> None:
        state, _ = state_mod.load(self.project)
        before = state["_revision"]
        state_mod.save(self.project, state)
        self.assertEqual(state["_revision"], before + 1)
        state_mod.save(self.project, state)
        self.assertEqual(state["_revision"], before + 2)
        disk = json.loads((self.project / "aegis/mission.json").read_text())
        self.assertEqual(disk["_revision"], before + 2)

    def test_legacy_state_without_revision_upgrades_on_first_save(self) -> None:
        path = self.project / "aegis/mission.json"
        raw = json.loads(path.read_text())
        raw.pop("_revision", None)
        path.write_text(json.dumps(raw), encoding="utf-8")
        state, _ = state_mod.load(self.project)
        self.assertEqual(state["_revision"], 0)
        state_mod.save(self.project, state)
        self.assertEqual(state["_revision"], 1)

    def test_stale_writer_lock_is_recovered(self) -> None:
        lock = self.project / "aegis" / state_mod.LOCK_DIR_NAME
        lock.mkdir()
        old = time.time() - state_mod.LOCK_STALE_SECONDS - 5
        os.utime(lock, (old, old))
        state, _ = state_mod.load(self.project)
        state_mod.save(self.project, state)
        self.assertFalse(lock.exists())

    def test_symlinked_writer_lock_is_refused(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        outside = self.project / "outside"
        outside.mkdir()
        lock = self.project / "aegis" / state_mod.LOCK_DIR_NAME
        try:
            lock.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation not permitted")
        state, _ = state_mod.load(self.project)
        with self.assertRaisesRegex(state_mod.StateError, "symlink"):
            state_mod.save(self.project, state)


if __name__ == "__main__":
    unittest.main()
