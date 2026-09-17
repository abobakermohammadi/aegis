"""Regression tests for platform-aware evidence command splitting (#8)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))

from engine import core  # noqa: E402


class SplitCommandWindowsPaths(unittest.TestCase):
    def test_unquoted_windows_abs_path_preserves_backslashes(self):
        cmd = r"C:\Python39\python.exe -c print(1)"
        argv = core.split_command(cmd, posix=False)
        self.assertEqual(argv[0], r"C:\Python39\python.exe")
        self.assertEqual(argv[1:], ["-c", "print(1)"])

    def test_quoted_windows_path_with_spaces(self):
        cmd = r'"C:\Program Files\Python39\python.exe" -V'
        argv = core.split_command(cmd, posix=False)
        self.assertEqual(argv[0], r"C:\Program Files\Python39\python.exe")
        self.assertEqual(argv[1:], ["-V"])

    def test_mixed_args_keep_boundaries(self):
        cmd = r"C:\Tools\bin\tool.exe --out C:\Temp\out.txt --flag"
        argv = core.split_command(cmd, posix=False)
        self.assertEqual(
            argv,
            [r"C:\Tools\bin\tool.exe", "--out", r"C:\Temp\out.txt", "--flag"],
        )


class SplitCommandPosix(unittest.TestCase):
    def test_posix_quoting_preserved(self):
        argv = core.split_command("echo 'hello world'", posix=True)
        self.assertEqual(argv, ["echo", "hello world"])

    def test_posix_simple_argv(self):
        self.assertEqual(
            core.split_command("pytest -q tests", posix=True),
            ["pytest", "-q", "tests"],
        )

    def test_posix_still_consumes_backslash_escapes(self):
        argv = core.split_command(r"C:\Python39\python.exe -c print(1)", posix=True)
        self.assertEqual(argv[0], r"C:Python39python.exe")


class RunCommandUsesSplit(unittest.TestCase):
    def test_argv_and_backslashes_reach_subprocess(self):
        project = Path(".")
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = list(argv)

            class R:
                returncode = 0
                stdout = b"ok"
                stderr = b""

            return R()

        expected = [r"C:\Python39\python.exe", "-c", "print(1)"]
        with mock.patch.object(core, "split_command", return_value=expected), mock.patch(
            "subprocess.run", side_effect=fake_run
        ):
            result = core.run_command(project, r"C:\Python39\python.exe -c print(1)")

        self.assertEqual(result["exit"], 0)
        self.assertEqual(captured["argv"], expected)
        self.assertIsInstance(captured["argv"], list)


if __name__ == "__main__":
    unittest.main()
