#!/usr/bin/env python3
"""Cursor afterFileEdit hook: upload changed files via sftp_upload.py (no extra windows)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPLOAD = ROOT / "sftp_upload.py"
LOG = Path(__file__).resolve().parent / "sftp-upload.log"

SKIP_PREFIXES = (
    ".cursor/",
    ".git/",
    "node_modules/",
    "__pycache__/",
)


def _rel_path(file_path: str) -> str | None:
    path = Path(file_path)
    if not path.is_absolute():
        candidate = ROOT / path
        if candidate.is_file():
            path = candidate
        else:
            return normalize_rel(file_path)

    try:
        rel = path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return None

    rel_str = rel.as_posix()
    if not rel_str or any(rel_str.startswith(prefix) for prefix in SKIP_PREFIXES):
        return None
    return rel_str


def normalize_rel(path: str) -> str:
    rel = path.replace("\\", "/").lstrip("/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    file_path = None
    for key in ("file_path", "path", "filePath", "editedFile"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            file_path = value.strip()
            break

    if not file_path:
        return 0

    rel = _rel_path(file_path)
    if not rel or not UPLOAD.is_file():
        return 0

    local = ROOT / rel
    if not local.is_file():
        return 0

    kwargs: dict = {
        "args": [sys.executable, str(UPLOAD), rel],
        "cwd": str(ROOT),
        "capture_output": True,
        "text": True,
        "timeout": 90,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

    try:
        result = subprocess.run(**kwargs)
    except subprocess.TimeoutExpired:
        _log(rel, "TIMEOUT\n")
        return 0

    _log(rel, (result.stdout or "") + (result.stderr or ""))
    return 0


def _log(rel: str, body: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"\n--- {rel} ---\n")
        if body.strip():
            handle.write(body.rstrip() + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
