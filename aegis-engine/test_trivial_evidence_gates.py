"""Adversarial regression tests for trivial evidence completion gates."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))

from engine import core  # noqa: E402
from engine import gitinfo  # noqa: E402


class TrivialEvidenceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="aegis-trivial-gate-")
        self.project = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        subprocess.run([
            "git", "-C", str(self.project), "-c", "user.email=t@t",
            "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init"
        ], check=True)
        self.head = gitinfo.head_commit(self.project)
        self.criterion = {"id": "C1", "text": "real behavior works", "required": True,
                          "evidence": []}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def evidence(self, evidence_id: str, command: str, *, exit_code: int = 0) -> dict:
        return {
            "id": evidence_id,
            "criterion": "C1",
            "kind": "test",
            "command": command,
            "exit": exit_code,
            "summary": "ok",
            "commit": self.head,
            "files": [],
            "captured_at": "2026-09-17T00:00:00+00:00",
            "verified": True,
        }

    def status_for(self, *evidence: dict) -> tuple[str, list[str]]:
        self.criterion["evidence"] = [item["id"] for item in evidence]
        st = {"evidence": list(evidence)}
        return core.gate_status(self.project, st, self.criterion)

    def test_true_cannot_satisfy_required_gate(self) -> None:
        status, reasons = self.status_for(self.evidence("E1", "true"))
        self.assertNotEqual(status, "pass", reasons)

    def test_colon_cannot_satisfy_required_gate(self) -> None:
        status, reasons = self.status_for(self.evidence("E1", ":"))
        self.assertNotEqual(status, "pass", reasons)

    def test_short_echo_cannot_satisfy_required_gate(self) -> None:
        status, reasons = self.status_for(self.evidence("E1", "echo ok"))
        self.assertNotEqual(status, "pass", reasons)

    def test_meaningful_success_still_passes(self) -> None:
        status, reasons = self.status_for(
            self.evidence("E1", f'{sys.executable} -c "print(42)"')
        )
        self.assertEqual(status, "pass", reasons)

    def test_trivial_plus_meaningful_success_passes(self) -> None:
        status, reasons = self.status_for(
            self.evidence("E1", "true"),
            self.evidence("E2", f'{sys.executable} -c "print(42)"'),
        )
        self.assertEqual(status, "pass", reasons)


if __name__ == "__main__":
    unittest.main()
