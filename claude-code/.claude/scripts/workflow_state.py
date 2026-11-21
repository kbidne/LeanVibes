#!/usr/bin/env python3
"""Shell steps for /review-loop and /backlog-sprint, one command each.

The command files call this script instead of multi-line shell snippets.
Claude Code's permission rules match command text, so a snippet that starts
with ``VAR=...``, chains several commands or writes into ``.git/`` with
``mkdir``, ``rm`` or ``>>`` is denied under a prefix allowlist (and always
denied in ``dontAsk`` mode for ``.git/``). A single ``python3
.claude/scripts/workflow_state.py ...`` call matches one rule.

Every subcommand prints one JSON object on stdout.

    paths [--worktree W]
        {"main", "base", "git_dir", "common_dir"}: the main checkout, the
        default branch, and the git dirs of W (default: the current dir).
    now
        {"now": "<UTC ISO time>"}
    statedir NAME [--worktree W | --common]
        Create and print the state dir NAME inside W's private git dir, or
        inside the main repository's git dir with --common.
    lock acquire|release|show NAME [--worktree W | --common] [--pid P]
        The lock file NAME/lock holds {"pid", "started_at"}. pid is this
        Claude Code session (found by walking up the process tree; --pid
        overrides). acquire: exit 0 if taken (a dead or own pid is replaced),
        exit 3 if a live other session holds it. release: removes the lock
        only if it is ours (exit 3 otherwise). show: the lock, "alive" and
        "ours".
    metrics-append FILE JSON
        Append one JSON line to FILE in the main repository's git dir.
    metrics-show --pr M [--file FILE]
        {"record": <the highest-run "run" line for PR M, or null>}
    check lint|test --worktree W [--tests PATH ...]
        Run review-loop.json's lint_commands, or its test_command with
        {tests} replaced by the paths (empty: the whole suite), with W as the
        working directory, so relative commands like .venv/bin/python resolve
        inside it. {"ok", "results": [{"command", "exit", "output"}]}.
        Exit 0 all passed, 4 one failed, 2 nothing configured.
    worktree find BRANCH
        {"path": <worktree with BRANCH checked out, or null>}
    worktree add NAME BRANCH [--start REF] [--link PATH ...]
        git worktree add <main>/.claude/worktrees/NAME -B BRANCH REF
        (REF defaults to origin/BRANCH, fetched first), then symlink each
        --link path (e.g. .venv, .env) from the main checkout if it exists.
        If another worktree already has BRANCH checked out, print that one
        with "existing": true instead.
    worktree remove PATH
        Remove the untracked top-level symlinks in PATH, then
        git worktree remove PATH (never --force).
    overlap BASE [--worktree W]
        Files changed both on origin/BASE and on W's HEAD since their
        merge base: {"merge_base", "files"}.

Exit 0: done. Exit 3: lock held by someone else. Exit 4: a check failed.
Exit 1: a git command failed (stderr has its message). Exit 2: bad
arguments or nothing configured.
Standard library only, Python 3.8+.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


class GitError(RuntimeError):
    pass


def git(args: List[str], cwd: Optional[str] = None) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


def emit(obj) -> None:
    print(json.dumps(obj))


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main_checkout(cwd: Optional[str] = None) -> str:
    for line in git(["worktree", "list", "--porcelain"], cwd).splitlines():
        if line.startswith("worktree "):
            return line[len("worktree "):]
    raise GitError("git worktree list: no worktrees")


def default_branch(cwd: Optional[str] = None) -> str:
    try:
        ref = git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd).strip()
    except GitError:
        return "main"
    return ref[len("origin/"):] if ref.startswith("origin/") else (ref or "main")


def git_dir(cwd: Optional[str], common: bool = False) -> Path:
    flag = "--git-common-dir" if common else "--git-dir"
    return Path(git(["rev-parse", "--path-format=absolute", flag], cwd).strip())


def state_dir(name: str, worktree: Optional[str], common: bool) -> Path:
    d = git_dir(worktree, common) / name
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- session pid -----------------------------------------------------------

def _ps(pid: int):
    proc = subprocess.run(["ps", "-o", "ppid=", "-o", "args=", "-p", str(pid)],
                          capture_output=True, text=True)
    out = proc.stdout.strip()
    if proc.returncode != 0 or not out:
        return None
    ppid, _, args = out.partition(" ")
    try:
        return int(ppid), args.strip()
    except ValueError:
        return None


def is_claude(args: str) -> bool:
    """The process is Claude Code: the claude binary, or node running its cli.js."""
    parts = args.split()
    if not parts:
        return False
    exe = os.path.basename(parts[0])
    if exe == "claude":
        return True
    return exe in ("node", "bun") and len(parts) > 1 and (
        parts[1].endswith("/claude") or "@anthropic-ai/claude-code/" in parts[1])


def session_pid() -> int:
    """The nearest ancestor that is Claude Code, else the nearest non-shell one."""
    pid = os.getppid()
    fallback = None
    for _ in range(12):
        info = _ps(pid)
        if info is None:
            break
        ppid, args = info
        if is_claude(args):
            return pid
        name = os.path.basename(args.split(" ", 1)[0]).lstrip("-")
        if fallback is None and name not in ("sh", "bash", "zsh", "dash", "fish"):
            fallback = pid
        if ppid <= 1:
            break
        pid = ppid
    return fallback if fallback is not None else os.getppid()


def pid_alive(pid) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# --- lock -------------------------------------------------------------------

def read_lock(path: Path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {"pid": None, "started_at": None, "malformed": True}


def _create(path: Path, pid: int) -> bool:
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps({"pid": pid, "started_at": now()}) + "\n")
    return True


def lock_acquire(d: Path, pid: int) -> int:
    path = d / "lock"
    replaced = None
    for _ in range(2):
        if _create(path, pid):
            emit({"acquired": True, "lock": str(path), "pid": pid, "replaced": replaced})
            return 0
        held = read_lock(path)
        if held is None:
            continue  # removed between our create and read: try again
        if held.get("pid") != pid and pid_alive(held.get("pid")):
            emit({"acquired": False, "lock": str(path), "holder": held})
            return 3
        replaced = held  # stale (dead pid) or our own (a resume)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    emit({"acquired": False, "lock": str(path), "holder": read_lock(path)})
    return 3


def lock_release(d: Path, pid: int) -> int:
    path = d / "lock"
    held = read_lock(path)
    if held is None:
        emit({"released": False, "lock": str(path), "reason": "no lock"})
        return 0
    if held.get("pid") != pid and not held.get("malformed"):
        emit({"released": False, "lock": str(path), "holder": held, "reason": "not ours"})
        return 3
    path.unlink()
    emit({"released": True, "lock": str(path)})
    return 0


def lock_show(d: Path, pid: int) -> int:
    path = d / "lock"
    held = read_lock(path)
    emit({"lock": str(path), "holder": held,
          "alive": bool(held) and pid_alive(held.get("pid")),
          "ours": bool(held) and held.get("pid") == pid})
    return 0


# --- worktrees --------------------------------------------------------------

def worktree_find(branch: str, cwd: Optional[str] = None) -> Optional[str]:
    path = None
    for line in git(["worktree", "list", "--porcelain"], cwd).splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line == f"branch refs/heads/{branch}":
            return path
    return None


def worktree_add(name: str, branch: str, start: Optional[str], links: List[str]) -> dict:
    main = main_checkout()
    existing = worktree_find(branch, main)
    if existing is not None and Path(existing) != Path(main):
        # Already checked out in another worktree (e.g. the implementer's):
        # use that one rather than failing on a second checkout.
        return {"path": existing, "branch": branch, "start": None, "linked": [],
                "existing": True}
    path = Path(main) / ".claude" / "worktrees" / name
    if path.exists():
        raise GitError(f"{path} already exists")
    if start is None:
        git(["fetch", "-q", "origin", branch], main)
        start = f"origin/{branch}"
    path.parent.mkdir(parents=True, exist_ok=True)
    git(["worktree", "add", "-q", str(path), "-B", branch, start], main)
    linked = []
    for rel in links:
        src, dst = Path(main) / rel, path / rel
        if src.exists() and not dst.exists() and not dst.is_symlink():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.symlink_to(src)
            linked.append(rel)
    return {"path": str(path), "branch": branch, "start": start, "linked": linked}


def worktree_remove(path: str) -> dict:
    p = Path(path)
    unlinked = []
    for entry in sorted(p.iterdir()):
        if not entry.is_symlink():
            continue
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", entry.name],
                                 cwd=str(p), capture_output=True).returncode == 0
        if not tracked:
            entry.unlink()
            unlinked.append(entry.name)
    git(["worktree", "remove", str(p)], main_checkout(str(p)))
    return {"removed": str(p), "unlinked": unlinked}


def overlap(base: str, worktree: Optional[str]) -> dict:
    git(["fetch", "-q", "origin", base], worktree)
    mb = git(["merge-base", f"origin/{base}", "HEAD"], worktree).strip()
    theirs = set(git(["diff", "--name-only", mb, f"origin/{base}"], worktree).split())
    ours = set(git(["diff", "--name-only", mb, "HEAD"], worktree).split())
    return {"merge_base": mb, "files": sorted(theirs & ours)}


# --- metrics and checks -----------------------------------------------------

def metrics_show(pr: int, file: str) -> Optional[dict]:
    path = git_dir(None, common=True) / Path(file).name
    best = None
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return None
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("type") == "run" and rec.get("pr") == pr and (
                best is None or (rec.get("run") or 0) >= (best.get("run") or 0)):
            best = rec
    return best


def load_config(worktree: str) -> dict:
    for root in (Path(worktree), Path(main_checkout(worktree))):
        path = root / ".claude" / "review-loop.json"
        if path.is_file():
            return json.loads(path.read_text())
    return {}


def check(kind: str, worktree: str, tests: List[str], tail: int = 4000):
    cfg = load_config(worktree)
    if kind == "lint":
        commands = list(cfg.get("lint_commands") or [])
    else:
        cmd = cfg.get("test_command")
        joined = " ".join(shlex.quote(t) for t in tests)
        commands = [cmd.replace("{tests}", joined).strip()] if cmd else []
    if not commands:
        return 2, {"ok": False, "results": [],
                   "reason": f"no {'lint_commands' if kind == 'lint' else 'test_command'} in review-loop.json"}
    results = []
    for cmd in commands:
        proc = subprocess.run(cmd, shell=True, cwd=worktree, capture_output=True, text=True)
        out = (proc.stdout + proc.stderr)[-tail:]
        results.append({"command": cmd, "exit": proc.returncode, "output": out})
    ok = all(r["exit"] == 0 for r in results)
    return (0 if ok else 4), {"ok": ok, "worktree": worktree, "results": results}


# --- cli --------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("paths")
    sp.add_argument("--worktree")
    sub.add_parser("now")

    def where(sp):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--worktree")
        g.add_argument("--common", action="store_true")

    sp = sub.add_parser("statedir")
    sp.add_argument("name")
    where(sp)

    sp = sub.add_parser("lock")
    sp.add_argument("action", choices=["acquire", "release", "show"])
    sp.add_argument("name")
    where(sp)
    sp.add_argument("--pid", type=int)

    sp = sub.add_parser("metrics-append")
    sp.add_argument("file")
    sp.add_argument("json")

    sp = sub.add_parser("metrics-show")
    sp.add_argument("--pr", type=int, required=True)
    sp.add_argument("--file", default="review-loop-metrics.jsonl")

    sp = sub.add_parser("check")
    sp.add_argument("kind", choices=["lint", "test"])
    sp.add_argument("--worktree", required=True)
    sp.add_argument("--tests", nargs="*", default=[])

    sp = sub.add_parser("worktree")
    wsub = sp.add_subparsers(dest="wcmd", required=True)
    w = wsub.add_parser("find")
    w.add_argument("branch")
    w = wsub.add_parser("add")
    w.add_argument("name")
    w.add_argument("branch")
    w.add_argument("--start")
    w.add_argument("--link", action="append", default=[])
    w = wsub.add_parser("remove")
    w.add_argument("path")

    sp = sub.add_parser("overlap")
    sp.add_argument("base")
    sp.add_argument("--worktree")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    a = build_parser().parse_args(argv)
    try:
        if a.cmd == "paths":
            emit({"main": main_checkout(a.worktree), "base": default_branch(a.worktree),
                  "git_dir": str(git_dir(a.worktree)),
                  "common_dir": str(git_dir(a.worktree, common=True))})
        elif a.cmd == "now":
            emit({"now": now()})
        elif a.cmd == "statedir":
            emit({"dir": str(state_dir(a.name, a.worktree, a.common))})
        elif a.cmd == "lock":
            d = state_dir(a.name, a.worktree, a.common)
            pid = a.pid if a.pid is not None else session_pid()
            return {"acquire": lock_acquire, "release": lock_release,
                    "show": lock_show}[a.action](d, pid)
        elif a.cmd == "metrics-append":
            try:
                record = json.loads(a.json)
            except ValueError as e:
                print(f"metrics-append: not JSON: {e}", file=sys.stderr)
                return 2
            target = git_dir(None, common=True) / Path(a.file).name
            with open(target, "a") as f:
                f.write(json.dumps(record, separators=(",", ":")) + "\n")
            emit({"appended": str(target)})
        elif a.cmd == "metrics-show":
            emit({"record": metrics_show(a.pr, a.file)})
        elif a.cmd == "check":
            code, out = check(a.kind, a.worktree, a.tests)
            emit(out)
            return code
        elif a.cmd == "worktree":
            if a.wcmd == "find":
                emit({"path": worktree_find(a.branch)})
            elif a.wcmd == "add":
                emit(worktree_add(a.name, a.branch, a.start, a.link))
            else:
                emit(worktree_remove(a.path))
        elif a.cmd == "overlap":
            emit(overlap(a.base, a.worktree))
    except GitError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
