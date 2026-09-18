"""Aegis Mission Engine package."""

# Make human CLI output safe on legacy (non-UTF-8) consoles (#9).
# Importing the package wraps stdout/stderr once; UTF-8 terminals keep glyphs,
# constrained encodings get deterministic ASCII fallbacks. JSON dumps stay
# ASCII-safe via json.dumps(ensure_ascii=True) and are unchanged.
from . import safe_io as _safe_io

_safe_io.install()
