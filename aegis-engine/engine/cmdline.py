"""Platform-aware command-line splitting for evidence commands (#8)."""

from __future__ import annotations


def split_command(command: str, *, posix: bool | None = None) -> list[str]:
    """Split a command string into argv without invoking a shell.

    On Windows (posix=False), backslashes in absolute paths are preserved so
    values like ``C:\\Python\\python.exe`` reach subprocess unchanged.
    Surrounding quotes used to protect spaces are stripped from tokens.
    On POSIX (posix=True), standard POSIX quoting rules are preserved.
    When *posix* is omitted, the host platform is used.
    """
    import os
    import shlex

    if posix is None:
        posix = os.name != "nt"
    if posix:
        return shlex.split(command, posix=True)
    parts = shlex.split(command, posix=False)
    out: list[str] = []
    for part in parts:
        if len(part) >= 2 and part[0] == part[-1] and part[0] in ('"', "'"):
            part = part[1:-1]
        out.append(part)
    return out
