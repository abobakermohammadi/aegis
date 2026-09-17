"""Safe stdout/stderr writes for non-UTF-8 consoles (#9).

Human CLI output may include status glyphs (\u2713 \u00d7 \u2014 \u2192). On legacy Windows
code pages those characters are unencodable and a bare ``print`` can raise
``UnicodeEncodeError``. This module:

* preserves glyphs when the stream encoding can represent them;
* substitutes deterministic ASCII fallbacks for known glyphs otherwise;
* replaces any remaining unencodable characters so writes never crash.

Machine-readable JSON paths are unaffected: ``json.dumps`` defaults to
``ensure_ascii=True``, producing ASCII-only output.
"""

from __future__ import annotations

import sys
from typing import Any, TextIO

# Deterministic ASCII stand-ins used only when the target encoding cannot
# represent the glyph. Order does not matter; replacements are disjoint.
GLYPH_FALLBACKS: dict[str, str] = {
    "\u2713": "OK",  # check mark
    "\u00d7": "X",   # multiplication sign
    "\u2014": "-",   # em dash
    "\u2192": "->",  # right arrow
}


def _normalize_encoding(encoding: str | None) -> str:
    if not encoding:
        return "utf-8"
    name = encoding.lower().replace("_", "-")
    if name in ("utf8", "utf-8", "utf-8-sig", "u8"):
        return "utf-8"
    return encoding


def can_encode(text: str, encoding: str | None) -> bool:
    """Return True when *text* encodes cleanly in *encoding*."""
    enc = _normalize_encoding(encoding)
    try:
        text.encode(enc)
        return True
    except (LookupError, UnicodeEncodeError):
        return False


def sanitize_for_encoding(text: str, encoding: str | None) -> str:
    """Return *text* adapted so it can be written to a stream with *encoding*.

    Known status glyphs are remapped to ASCII equivalents only when the
    encoding cannot represent them. Any leftover unencodable characters are
    replaced with ``?`` (via ``errors='replace'``) so the write cannot raise
    ``UnicodeEncodeError``.
    """
    if text is None:
        return text
    enc = _normalize_encoding(encoding)
    if can_encode(text, enc):
        return text
    out = text
    for glyph, repl in GLYPH_FALLBACKS.items():
        if glyph in out and not can_encode(glyph, enc):
            out = out.replace(glyph, repl)
    if can_encode(out, enc):
        return out
    return out.encode(enc, errors="replace").decode(enc)


def safe_write(stream: TextIO, text: str) -> int:
    """Write *text* to *stream*, sanitizing for the stream's encoding."""
    encoding = getattr(stream, "encoding", None)
    return stream.write(sanitize_for_encoding(text, encoding))


def safe_print(*args: Any, sep: str = " ", end: str = "\n",
               file: TextIO | None = None, flush: bool = False) -> None:
    """``print`` that never raises ``UnicodeEncodeError`` on constrained consoles."""
    stream = file if file is not None else sys.stdout
    encoding = getattr(stream, "encoding", None)
    pieces = [sanitize_for_encoding(str(a), encoding) for a in args]
    body = sanitize_for_encoding(sep, encoding).join(pieces)
    body += sanitize_for_encoding(end, encoding)
    stream.write(body)
    if flush:
        try:
            stream.flush()
        except Exception:
            pass


class SafeTextIO:
    """Thin wrapper that sanitizes ``write``/``writelines`` for stream encoding."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    @property
    def encoding(self) -> str | None:
        return getattr(self._stream, "encoding", None)

    def write(self, s: str) -> int:  # type: ignore[override]
        if not isinstance(s, str):
            return self._stream.write(s)
        return self._stream.write(sanitize_for_encoding(s, self.encoding))

    def writelines(self, lines) -> None:  # type: ignore[override]
        for line in lines:
            self.write(line)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def install(stdout: bool = True, stderr: bool = True) -> None:
    """Wrap ``sys.stdout`` / ``sys.stderr`` so human CLI prints stay crash-free.

    Idempotent: skips streams that are already ``SafeTextIO`` wrappers.
    Does not alter JSON semantics — ASCII-escaped ``json.dumps`` output is a
    no-op under sanitization.
    """
    if stdout and not isinstance(sys.stdout, SafeTextIO):
        sys.stdout = SafeTextIO(sys.stdout)  # type: ignore[assignment]
    if stderr and not isinstance(sys.stderr, SafeTextIO):
        sys.stderr = SafeTextIO(sys.stderr)  # type: ignore[assignment]
