"""Regression tests for objective benchmark scoring."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


score = load_module("aegis_benchmark_score", HERE / "score.py")
generator = load_module("aegis_benchmark_generator", HERE / "generate_fixture.py")


class BenchmarkScorerIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="aegis-benchmark-score-")
        self.root = Path(self._tmp.name) / "fixture"
        generator.generate(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_planted_security_defect_fails_behavioral_score(self) -> None:
        self.assertFalse(score.d4_no_eval(self.root))
        self.assertFalse((self.root / ".aegis-d4-code-executed").exists())

    def test_exec_substitution_cannot_game_security_score(self) -> None:
        (self.root / "sanitizer.py").write_text(
            "def clean(text: str) -> str:\n    exec(text)\n    return text\n",
            encoding="utf-8",
        )
        self.assertFalse(score.d4_no_eval(self.root))

    def test_nonexecuting_sanitizer_passes_security_score(self) -> None:
        (self.root / "sanitizer.py").write_text(
            "def clean(text: str) -> str:\n    return text.replace('<', '&lt;')\n",
            encoding="utf-8",
        )
        self.assertTrue(score.d4_no_eval(self.root))

    def test_empty_export_file_does_not_satisfy_documented_feature(self) -> None:
        (self.root / "export.py").write_text("# placeholder\n", encoding="utf-8")
        self.assertFalse(score.d5_doc_matches_reality(self.root))

    def test_working_export_command_satisfies_documented_feature(self) -> None:
        (self.root / "export.py").write_text(
            "from pathlib import Path\nPath('notes.csv').write_text('note\\nhello\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        self.assertTrue(score.d5_doc_matches_reality(self.root))


if __name__ == "__main__":
    unittest.main()
