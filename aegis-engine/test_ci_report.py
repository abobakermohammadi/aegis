"""End-to-end tests for the machine-readable Aegis CI report."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
AEGIS = [sys.executable, str(ENGINE / "aegis.py")]
AEGIS_CI = [sys.executable, str(ENGINE / "aegis_ci.py")]


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        capture_output=True,
        check=True,
    )


class CiReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="aegis-ci-report ")
        self.base = Path(self._tmp.name)
        self.project = self.base / "project with spaces"
        self.project.mkdir()
        git(self.project, "init", "-q")
        (self.project / "app.py").write_text("x = 1\n")
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "initial")
        r = run(AEGIS + ["init", "--goal", "ship safely", "--criterion", "tests pass"], self.project)
        self.assertEqual(r.returncode, 0, r.stderr)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def report(self, *args: str) -> subprocess.CompletedProcess:
        return run(AEGIS_CI + ["--project", str(self.project), *args], self.base)

    def test_json_report_is_parseable_and_project_scoped(self) -> None:
        r = self.report()
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["mission"]["goal"], "ship safely")
        self.assertEqual(payload["gates"]["required_total"], 1)
        self.assertFalse(payload["ready_to_complete"])
        self.assertEqual(payload["git"]["head"], subprocess.check_output(
            ["git", "-C", str(self.project), "rev-parse", "HEAD"], text=True
        ).strip())

    def test_require_complete_fails_closed_until_gate_passes(self) -> None:
        r = self.report("--require-complete")
        self.assertEqual(r.returncode, 1)

        r = run(
            AEGIS + [
                "evidence", "add", "-c", "C1", "--run",
                sys.executable + " -c \"print('ok')\"", "--files", "app.py",
            ],
            self.project,
        )
        self.assertEqual(r.returncode, 0, r.stderr)

        r = self.report("--require-complete")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        payload = json.loads(r.stdout)
        self.assertTrue(payload["ready_to_complete"])
        self.assertEqual(payload["gates"]["criteria"][0]["status"], "pass")

    def test_stale_evidence_is_visible_and_fails_completion_gate(self) -> None:
        r = run(
            AEGIS + [
                "evidence", "add", "-c", "C1", "--run",
                sys.executable + " -c \"print('ok')\"", "--files", "app.py",
            ],
            self.project,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        (self.project / "app.py").write_text("x = 2\n")
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "change guarded file")

        r = self.report("--require-complete")
        self.assertEqual(r.returncode, 1)
        payload = json.loads(r.stdout)
        self.assertFalse(payload["ready_to_complete"])
        self.assertEqual(payload["gates"]["criteria"][0]["status"], "stale")

    def test_missing_state_returns_json_error_and_exit_2(self) -> None:
        empty = self.base / "empty"
        empty.mkdir()
        r = run(AEGIS_CI + ["--project", str(empty)], self.base)
        self.assertEqual(r.returncode, 2)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["schema_version"], 1)
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
