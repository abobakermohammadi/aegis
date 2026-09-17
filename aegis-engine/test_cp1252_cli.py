"""Regression coverage for Windows legacy-console CLI output compatibility."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
CLI = ENGINE / "aegis.py"


class Cp1252CliTests(unittest.TestCase):
    def _run(self, project: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "cp1252"
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=str(project), env=env, capture_output=True, text=True,
            encoding="cp1252", errors="strict", check=False,
        )

    def test_status_with_passing_gate_is_cp1252_safe(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aegis-cp1252-") as tmp:
            project = Path(tmp)
            init = self._run(project, "init", "--goal", "portable output", "--criterion", "smoke")
            self.assertEqual(init.returncode, 0, init.stderr)
            evidence = self._run(project, "evidence", "add", "-c", "C1", "--run", f'"{sys.executable}" -c "print(1)"')
            self.assertEqual(evidence.returncode, 0, evidence.stderr)
            status = self._run(project, "status")
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertNotIn("UnicodeEncodeError", status.stderr)
            self.assertIn("all required gates pass", status.stdout)

    def test_open_gate_status_is_cp1252_safe(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aegis-cp1252-open-") as tmp:
            project = Path(tmp)
            init = self._run(project, "init", "--goal", "portable output", "--criterion", "smoke")
            self.assertEqual(init.returncode, 0, init.stderr)
            status = self._run(project, "status")
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertNotIn("UnicodeEncodeError", status.stderr)


if __name__ == "__main__":
    unittest.main()
