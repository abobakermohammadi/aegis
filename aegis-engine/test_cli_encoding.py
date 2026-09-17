"""Regression tests: CLI human output on non-UTF-8 consoles (#9).

Constrains stdout/stderr to cp1252/ascii (strict) and asserts representative
CLI paths never raise UnicodeEncodeError, while UTF-8 consoles keep glyphs.
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))

from engine import safe_io  # noqa: E402
from engine import state as state_mod  # noqa: E402
import aegis as cli  # noqa: E402


def _strict_text_stream(encoding: str) -> tuple[io.BytesIO, io.TextIOWrapper]:
    buf = io.BytesIO()
    stream = io.TextIOWrapper(
        buf, encoding=encoding, errors="strict", newline="\n", write_through=True
    )
    return buf, stream


def _decode(buf: io.BytesIO, encoding: str) -> str:
    return buf.getvalue().decode(encoding, errors="replace")


class SanitizeHelpers(unittest.TestCase):
    def test_utf8_preserves_glyphs(self):
        sample = "gates \u2713  blocked \u00d7  dash \u2014  arrow \u2192"
        self.assertEqual(safe_io.sanitize_for_encoding(sample, "utf-8"), sample)

    def test_cp1252_falls_back_unencodable_glyphs(self):
        # \u00d7 (U+00D7) and \u2014 (U+2014) exist in cp1252; \u2713 and \u2192 do not.
        out = safe_io.sanitize_for_encoding("\u2713 \u00d7 \u2014 \u2192", "cp1252")
        self.assertEqual(out, "OK \u00d7 \u2014 ->")
        out.encode("cp1252")  # must not raise

    def test_ascii_falls_back_all_known_glyphs(self):
        out = safe_io.sanitize_for_encoding("\u2713 done \u00d7 fail \u2014 note \u2192 next", "ascii")
        self.assertEqual(out, "OK done X fail - note -> next")
        out.encode("ascii")

    def test_unknown_unencodable_replaced(self):
        out = safe_io.sanitize_for_encoding("snowman \u2603", "ascii")
        self.assertNotIn("\u2603", out)
        out.encode("ascii")


class SafeTextIOStream(unittest.TestCase):
    def test_raw_cp1252_raises_without_wrapper(self):
        _buf, stream = _strict_text_stream("cp1252")
        with self.assertRaises(UnicodeEncodeError):
            stream.write("status \u2713\n")

    def test_wrapper_cp1252_does_not_raise(self):
        buf, stream = _strict_text_stream("cp1252")
        safe = safe_io.SafeTextIO(stream)
        safe.write("status \u2713 blocked \u00d7 dash \u2014 arrow \u2192\n")
        stream.flush()
        text = _decode(buf, "cp1252")
        self.assertIn("OK", text)
        self.assertIn("->", text)
        self.assertNotIn("\u2713", text)
        self.assertNotIn("\u2192", text)

    def test_wrapper_utf8_preserves(self):
        buf, stream = _strict_text_stream("utf-8")
        safe = safe_io.SafeTextIO(stream)
        safe.write("\u2713 \u00d7 \u2014 \u2192\n")
        stream.flush()
        self.assertEqual(_decode(buf, "utf-8"), "\u2713 \u00d7 \u2014 \u2192\n")


class _CliEncodingCase(unittest.TestCase):
    """Drive real CLI command functions against a constrained stdout/stderr."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="aegis-enc-")
        self.project = Path(self._tmp.name) / "proj"
        self.project.mkdir()
        st = state_mod.empty_state("Ship encoding-safe CLI", "portability")
        st["criteria"].append(
            {
                "id": "C1",
                "text": "gates readable",
                "required": True,
                "evidence": [],
                "blocked_reason": None,
            }
        )
        # Force a blocked criterion so status emits \u00d7.
        st["criteria"].append(
            {
                "id": "C2",
                "text": "blocked gate",
                "required": True,
                "evidence": [],
                "blocked_reason": "waiting on secrets",
            }
        )
        state_mod.save(self.project, st)
        self._orig_out = sys.stdout
        self._orig_err = sys.stderr

    def tearDown(self) -> None:
        sys.stdout = self._orig_out
        sys.stderr = self._orig_err
        self._tmp.cleanup()

    def _install(self, encoding: str) -> tuple[io.BytesIO, io.BytesIO]:
        out_buf, out_stream = _strict_text_stream(encoding)
        err_buf, err_stream = _strict_text_stream(encoding)
        sys.stdout = safe_io.SafeTextIO(out_stream)  # type: ignore[assignment]
        sys.stderr = safe_io.SafeTextIO(err_stream)  # type: ignore[assignment]
        return out_buf, err_buf

    def _args(self, **kwargs):
        base = {"project": str(self.project), "repair": False, "rerun": False,
                "force": False, "checkpoint": None}
        base.update(kwargs)
        return SimpleNamespace(**base)

    def _run_paths(self, encoding: str) -> str:
        out_buf, err_buf = self._install(encoding)
        # status (glyphs: \u00d7 for blocked, \u2014 in reasons); return codes may be
        # non-zero for unmet gates — we only care that encoding never crashes.
        cli.cmd_status(self._args(), self.project)
        cli.cmd_verify(self._args(rerun=False), self.project)
        cli.cmd_doctor(self._args(repair=False), self.project)
        cli.cmd_resume(self._args(), self.project)
        # failure diagnostics: complete refuses with stderr details
        code = cli.cmd_complete(self._args(force=False), self.project)
        self.assertEqual(code, 1)
        out_stream = sys.stdout._stream  # type: ignore[attr-defined]
        err_stream = sys.stderr._stream  # type: ignore[attr-defined]
        out_stream.flush()
        err_stream.flush()
        return _decode(out_buf, encoding) + "\n" + _decode(err_buf, encoding)


class CliPathsNonUtf8(_CliEncodingCase):
    def test_cp1252_cli_paths_do_not_crash(self):
        text = self._run_paths("cp1252")
        # Unencodable glyphs must have been remapped.
        self.assertNotIn("\u2713", text)
        self.assertNotIn("\u2192", text)
        self.assertTrue("blocked" in text or "C2" in text)
        self.assertIn("cannot complete", text)

    def test_ascii_cli_paths_do_not_crash(self):
        text = self._run_paths("ascii")
        self.assertNotIn("\u2713", text)
        self.assertNotIn("\u00d7", text)
        self.assertNotIn("\u2014", text)
        self.assertNotIn("\u2192", text)
        # Deterministic ASCII fallbacks appear when those glyphs would have.
        # status blocked mark uses \u00d7 \u2192 X; resume uses \u2014 \u2192 -
        self.assertIn("X", text)  # blocked mark fallback
        self.assertIn("cannot complete", text)


class CliPathsUtf8Preserved(_CliEncodingCase):
    def test_utf8_preserves_blocked_and_dash_glyphs(self):
        # setUp leaves C2 blocked, so status emits \u00d7 and \u2014 on reasons.
        out_buf, _err_buf = self._install("utf-8")
        self.assertEqual(cli.cmd_status(self._args(), self.project), 0)
        sys.stdout._stream.flush()  # type: ignore[attr-defined]
        text = _decode(out_buf, "utf-8")
        self.assertIn("\u00d7", text)  # blocked mark
        self.assertIn("\u2014", text)  # reason separator


class JsonSemanticsUnchanged(unittest.TestCase):
    def test_json_dumps_default_is_ascii_safe(self):
        import json

        payload = {"mark": "\u2713", "arrow": "\u2192"}
        dumped = json.dumps(payload, sort_keys=True)
        dumped.encode("ascii")
        self.assertIn("\\u2713", dumped)
        self.assertIn("\\u2192", dumped)


if __name__ == "__main__":
    unittest.main()
