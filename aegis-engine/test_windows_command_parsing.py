"""Regression tests for Windows-style evidence command tokenization."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))

from engine import core  # noqa: E402


class WindowsCommandParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="aegis-win-command-")
        self.project = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _captured_argv(self, command: str) -> list[str]:
        completed = mock.Mock(returncode=0, stdout=b"ok\n", stderr=b"")
        with mock.patch.object(core.subprocess, "run", return_value=completed) as run:
            result = core.run_command(self.project, command)
        self.assertEqual(result["exit"], 0, result)
        return run.call_args.args[0]

    def test_unquoted_windows_absolute_path_preserves_backslashes(self) -> None:
        argv = self._captured_argv(r"C:\Python39\python.exe --version")
        self.assertEqual(argv, [r"C:\Python39\python.exe", "--version"])

    def test_quoted_windows_path_with_spaces_preserves_backslashes(self) -> None:
        argv = self._captured_argv(r'"C:\Program Files\Python\python.exe" --version')
        self.assertEqual(argv, [r"C:\Program Files\Python\python.exe", "--version"])

    def test_posix_quoting_behavior_remains_supported(self) -> None:
        argv = self._captured_argv("python -c \"print('hello world')\"")
        self.assertEqual(argv, ["python", "-c", "print('hello world')"])


if __name__ == "__main__":
    unittest.main()
