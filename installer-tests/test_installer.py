"""Cross-platform regression tests for install.py."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.py"


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="aegis-installer ")
        self.base = Path(self._tmp.name)
        self.target = self.base / "skills with spaces"
        self.engine = self.base / "engine with spaces"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_installer(self, *extra: str, smoke: bool = False) -> subprocess.CompletedProcess:
        args = [
            sys.executable,
            str(INSTALLER),
            "--target",
            str(self.target),
            "--engine-target",
            str(self.engine),
        ]
        if not smoke:
            args.append("--skip-smoke")
        args.extend(extra)
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, env=env, check=False)

    def backups_for(self, path: Path):
        return list(path.parent.glob(path.name + ".backup-*"))

    def test_clean_install_and_idempotent_reinstall(self) -> None:
        first = self.run_installer(smoke=True)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertTrue((self.target / "aegis-ceo-skills" / "SKILL.md").is_file())
        self.assertTrue((self.target / "usage-optimizer" / "SKILL.md").is_file())
        self.assertTrue((self.engine / "aegis.py").is_file())
        self.assertIn("verified: installed router answers correctly", first.stdout)

        second = self.run_installer()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("already installed", second.stdout)
        self.assertEqual(self.backups_for(self.target / "usage-optimizer"), [])
        self.assertEqual(self.backups_for(self.engine), [])

    def test_upgrade_backs_up_differing_copy(self) -> None:
        first = self.run_installer()
        self.assertEqual(first.returncode, 0, first.stderr)
        marker = self.target / "five-year-old" / "LOCAL_CHANGE.txt"
        marker.write_text("keep me in backup\n", encoding="utf-8")

        second = self.run_installer()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertFalse(marker.exists())
        backups = self.backups_for(self.target / "five-year-old")
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "LOCAL_CHANGE.txt").read_text(encoding="utf-8"), "keep me in backup\n")

    def test_keep_preserves_differing_copy(self) -> None:
        first = self.run_installer()
        self.assertEqual(first.returncode, 0, first.stderr)
        marker = self.target / "second-brain-context" / "LOCAL_CHANGE.txt"
        marker.write_text("do not replace\n", encoding="utf-8")

        second = self.run_installer("--keep")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertTrue(marker.is_file())
        self.assertIn("kept existing", second.stdout)
        self.assertEqual(self.backups_for(self.target / "second-brain-context"), [])

    def test_non_directory_obstruction_is_refused(self) -> None:
        self.target.mkdir(parents=True)
        obstruction = self.target / "usage-optimizer"
        obstruction.write_text("not a directory\n", encoding="utf-8")
        result = self.run_installer("--only", "usage-optimizer")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a directory", result.stderr)
        self.assertEqual(obstruction.read_text(encoding="utf-8"), "not a directory\n")

    def test_uninstall_is_reversible_backup(self) -> None:
        first = self.run_installer("--only", "five-year-old")
        self.assertEqual(first.returncode, 0, first.stderr)
        installed = self.target / "five-year-old"
        self.assertTrue(installed.is_dir())

        removed = self.run_installer("--only", "five-year-old", "--uninstall")
        self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
        self.assertFalse(installed.exists())
        backups = self.backups_for(installed)
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / "SKILL.md").is_file())
        self.assertFalse(self.engine.exists())
        self.assertEqual(len(self.backups_for(self.engine)), 1)

    def test_unknown_skill_fails_without_writing(self) -> None:
        result = self.run_installer("--only", "definitely-not-a-skill")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown skill", result.stderr)
        self.assertFalse(self.target.exists())
        self.assertFalse(self.engine.exists())


if __name__ == "__main__":
    unittest.main()
