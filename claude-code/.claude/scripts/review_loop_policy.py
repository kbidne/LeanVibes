#!/usr/bin/env python3
"""Classify a PR's changed files for /review-loop.

Reads ``.claude/review-loop.json`` (see ``review-loop.json.example``) and a
list of changed files, and prints one JSON object:

    {"risky": bool, "risky_files": [...],
     "auto_accept": bool, "always_ask_files": [...],
     "reasons": [...], "config": "<path or null>"}

- ``risky``: a file matches ``risky_paths``. A risky PR gets the stronger
  fixer model and never skips the closing review. It does not block a merge.
- ``auto_accept``: no file matches ``always_ask_paths``, so /review-loop may
  take its own recommended answer to a decision instead of stopping
  ("Default-accept"). With no config file, nothing is risky and nothing
  always asks, except that ``.github/workflows/`` always asks: a decision
  there can weaken a gate.

Usage::

    review_loop_policy.py --files files.txt [--config .claude/review-loop.json]
    git diff --name-only origin/main...HEAD | review_loop_policy.py --files -

Exit 0: auto-accept allowed. Exit 1: ask the user. Exit 2: bad arguments,
an unreadable file list, or a malformed config (the loop treats 2 as "ask").
Standard library only, Python 3.8+.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path
from typing import List, Optional

DEFAULT_CONFIG = Path(".claude/review-loop.json")
BUILTIN_ALWAYS_ASK = [".github/workflows/"]


def matches(path: str, pattern: str) -> bool:
    """True if ``path`` matches ``pattern``.

    A pattern ending in ``/`` is a directory prefix. Anything else is an
    fnmatch glob tried against the whole path and against the basename, so
    ``*.sql`` matches ``db/schema.sql``.
    """
    while path.startswith("./"):
        path = path[2:]
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(path.rsplit("/", 1)[-1], pattern)


def _patterns(config: dict, key: str) -> List[str]:
    value = config.get(key, [])
    if not isinstance(value, list) or not all(isinstance(p, str) and p for p in value):
        raise ValueError(f"{key} must be a list of non-empty strings")
    return value


def evaluate(files: List[str], config: dict) -> dict:
    risky_patterns = _patterns(config, "risky_paths")
    ask_patterns = _patterns(config, "always_ask_paths") + BUILTIN_ALWAYS_ASK

    risky_files: List[str] = []
    ask_files: List[str] = []
    reasons: List[str] = []
    for path in files:
        risky_hit = next((p for p in risky_patterns if matches(path, p)), None)
        if risky_hit:
            risky_files.append(path)
        ask_hit = next((p for p in ask_patterns if matches(path, p)), None)
        if ask_hit:
            ask_files.append(path)
            reasons.append(f"{path}: always-ask path {ask_hit}")
    return {
        "risky": bool(risky_files),
        "risky_files": risky_files,
        "auto_accept": not ask_files,
        "always_ask_files": ask_files,
        "reasons": reasons,
    }


def load_config(path: Optional[Path]) -> tuple:
    """Return (config dict, path used or None). Missing default file is not an error."""
    if path is None:
        path = DEFAULT_CONFIG
        if not path.exists():
            return {}, None
    with open(path, encoding="utf-8") as fh:
        config = json.load(fh)
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object")
    return config, str(path)


def _read_lines(path_or_dash: str) -> List[str]:
    text = sys.stdin.read() if path_or_dash == "-" else Path(path_or_dash).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--files", required=True, help="changed-file list, one per line, or -")
    parser.add_argument("--config", type=Path, default=None, help="default: .claude/review-loop.json if present")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2
    try:
        files = _read_lines(args.files)
        config, used = load_config(args.config)
        result = evaluate(files, config)
    except (OSError, ValueError) as exc:  # json.JSONDecodeError is a ValueError
        print(json.dumps({"error": str(exc)}))
        return 2
    result["config"] = used
    print(json.dumps(result))
    return 0 if result["auto_accept"] else 1


if __name__ == "__main__":
    sys.exit(main())
