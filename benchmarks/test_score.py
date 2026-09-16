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
score_m2 = load_module("aegis_benchmark_score_m2", HERE / "score_m2.py")
generator_m2 = load_module("aegis_benchmark_generator_m2", HERE / "generate_m2.py")


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


class M2ScorerIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="aegis-benchmark-m2-score-")
        self.root = Path(self._tmp.name) / "fixture"
        generator_m2.generate(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_injection_that_returns_all_rows_fails(self) -> None:
        self.assertFalse(score_m2.d4_no_sql_injection(self.root))

    def test_delete_stub_does_not_satisfy_documented_endpoint(self) -> None:
        # The planted fixture has a delete_task function, but it does not work.
        self.assertFalse(score_m2.d5_doc_matches_impl(self.root))

    def test_removing_unsupported_delete_claim_is_truthful(self) -> None:
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        (self.root / "README.md").write_text(
            readme.replace("- `DELETE /tasks/{id}` — remove a task. Returns 204.\n", ""),
            encoding="utf-8",
        )
        self.assertTrue(score_m2.d5_doc_matches_impl(self.root))


if __name__ == "__main__":
    unittest.main()
