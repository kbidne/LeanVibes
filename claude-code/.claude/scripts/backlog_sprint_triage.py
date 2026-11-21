#!/usr/bin/env python3
"""Triage open issues for /backlog-sprint.

Puts every open issue into exactly one group and prints the eligible ones in
queue order, with the skipped ones grouped by reason. `/backlog-sprint` runs
this once, shows the output, and asks the owner to approve the queue.

Groups, checked in this order (first match wins):

    skipped      a label listed in the config's `sprint.skip_labels`
    parked       any `waiting:*` label, or `stays open`
    epic         label `epic`
    ledger       label `review:ledger` (the review loop's ledger issue)
    not_code_fix no `type:bug`, `type:debt` or `type:enhancement` label
    in_progress  a worktree or an open PR already carries the issue number
    chain        filed by /review-loop at chain depth >= 2 (a follow-up of a
                 follow-up); listed per root issue for a design pass. Two
                 exceptions: a priority:high follow-up on a risky path stays
                 eligible, with a warning; and one filed after its root's
                 latest design note is listed under "Filed after the root's
                 design note" for a per-issue choice
    no_criteria  no `## Acceptance criteria` section with a `- [ ]` line
    low_value    filed by /review-loop, `priority:low` and tier 3, without the
                 `sprint:keep` label or a `## Why now` note. Not queued;
                 listed with its age for a close-as-not-worth-it sweep
    eligible     everything else, ordered by value per review round

Eligible order: tier 0 is due (an ISO date on a line that says due, deadline,
no later than, must land or land by, from 30 days ago to 14 days ahead); tier
1 is a risky path with evidence; tier 2 is one of risky path, evidence or
unblocks; tier 3 is the rest. Within a tier: priority, type (bug, debt,
enhancement), files cited (fewer first), issue number.

- Risky path: the body cites a path matching the config's `risky_paths`.
- Evidence: an `Introduced by: PR #N` line, a label in `sprint.evidence_labels`,
  or a line matching a regex in `sprint.evidence_patterns`.
- Unblocks: open issues parked `Parked: waiting:issue on #N` for it.

Stop rule: when every eligible issue is tier 3, there is no design pass and no
late follow-up, and none has a `## Why now` note or `priority:high`,
`tier3_only` is true and the output prints a STOP line. The sprint then
recommends an empty queue.

Every chain root with at least one skipped depth-2+ follow-up, and two or more
counting warned risky-path ones kept eligible, becomes a design-pass item,
listed before the eligible issues.

Extra sections: bundle candidates (eligible issues citing the same code file),
the ledger sweep (unchecked ledger lines on files an eligible issue cites),
and "may already be fixed" (issue numbers named by a commit on the default
branch: a prompt to read the commit, not proof).

Config: `.claude/review-loop.json` (keys `risky_paths` and `sprint.*`); all
optional. Usage:

    python3 .claude/scripts/backlog_sprint_triage.py --out triage.json

Standard library only, Python 3.8+. The classification is pure (`classify`,
`chain_depth`, `pr_issue`, `in_progress_numbers`, `why_now`, `tier`,
`order_eligible`, `design_passes`, `bundle_candidates`, `parse_ledger`) so it
is unit-tested without GitHub.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional, Set, Tuple

FOOTER = re.compile(r"Found by /review-loop[^\n]{0,80}?PR #(\d+)")
BRANCH_ISSUE = re.compile(r"^[a-z]+/(\d+)(?:\D|$)")
BODY_ISSUE = re.compile(r"\b(?:Closes|Fixes|Resolves|Refs)\s*:?\s*#(\d+)", re.IGNORECASE)
CRITERIA_HEADING = re.compile(r"^#{2,4}\s*Acceptance criteria", re.IGNORECASE | re.MULTILINE)
CHECKBOX = re.compile(r"^\s*- \[ \]", re.MULTILINE)
NUMBER_TOKEN = re.compile(r"(?<![A-Za-z.\d])(\d{1,6})(?![A-Za-z.\d])")

CODE_FIX_TYPES = ("type:bug", "type:debt", "type:enhancement")
PARKED_LABELS = ("stays open",)
PRIORITY_RANK = {"priority:high": 0, "priority:medium": 1, "priority:low": 2}
TYPE_RANK = {"type:bug": 0, "type:debt": 1, "type:enhancement": 2}
MAX_CHAIN_DEPTH = 1
PATCH_SEPARATELY_LABEL = "design:patch-separately"
KEEP_LABEL = "sprint:keep"
MIN_DESIGN_FOLLOWUPS = 2
DESIGN_NOTE = re.compile(r"^## Design note \(/backlog-sprint", re.MULTILINE)
LATE_CHOICES = ("patch", "close_fixed", "close_not_worth", "check")
MAX_BUNDLE = 3
MENTION = re.compile(r"#(\d+)\b")
MAX_MENTIONS_SHOWN = 2
MAX_LEDGER_SHOWN = 3
LEDGER_UNREACHABLE = re.compile(r"\bnot reachable\b", re.IGNORECASE)
LEDGER_PR = re.compile(r"^###\s+PR\s+#(\d+)")
LEDGER_FILE = re.compile(r"^\*\*(.+?)\*\*\s*$")
LEDGER_ENTRY = re.compile(
    r"^\s*- \[(?P<mark>[ xX])\]\s*\[(?P<cat>[\w-]+)\]\s*(?P<path>[^\s:]*):(?P<line>\d+)\s*[—-]+\s*(?P<text>.+)$")
DUE_DAYS = 14
OVERDUE_DAYS = 30

INTRODUCED_BY = re.compile(r"^Introduced by: PR #\d+", re.MULTILINE)
WHY_NOW_HEADING = re.compile(r"^#{2,4}\s*Why now\s*$", re.IGNORECASE | re.MULTILINE)
NEXT_HEADING = re.compile(r"^#{1,6}\s")
DUE_CUE = re.compile(r"\b(?:due(?!\s+to\b)|deadline|no later than|must land|land by)\b", re.IGNORECASE)
NOT_DUE_CUE = re.compile(r"\bnot before\b|\bafter\b", re.IGNORECASE)
ISO_DATE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
CODE_EXTS = ("py", "js", "jsx", "ts", "tsx", "mjs", "cjs", "go", "rs", "rb", "java", "kt", "swift", "c", "h",
             "cc", "cpp", "hpp", "cs", "php", "sh", "bash", "zsh", "sql", "html", "css", "scss", "vue", "svelte",
             "ex", "exs", "scala", "dart", "lua", "pl")
FILE_TOKEN = re.compile(r"(?<![\w/.-])[\w./-]+\.(?:" + "|".join(CODE_EXTS) + r")(?![\w-])")
PARKED_ON = re.compile(r"^Parked: waiting:issue on #(\d+)", re.MULTILINE)


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    body: str
    labels: Tuple[str, ...]
    created_at: str = ""  # GitHub `createdAt`, ISO 8601 UTC


@dataclass
class Verdict:
    group: str
    reason: str
    root_issue: Optional[int] = None
    chain_depth: int = 0
    warning: Optional[str] = None


@dataclass
class Config:
    risky_paths: List[str] = field(default_factory=list)
    skip_labels: List[str] = field(default_factory=list)
    evidence_labels: List[str] = field(default_factory=list)
    evidence_patterns: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict) -> "Config":
        sprint = raw.get("sprint") or {}
        if not isinstance(sprint, dict):
            raise ValueError("sprint must be an object")

        def strings(src: dict, key: str) -> List[str]:
            value = src.get(key, [])
            if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
                raise ValueError(f"{key} must be a list of non-empty strings")
            return value

        cfg = cls(strings(raw, "risky_paths"), strings(sprint, "skip_labels"),
                  strings(sprint, "evidence_labels"), strings(sprint, "evidence_patterns"))
        for p in cfg.evidence_patterns:
            try:
                re.compile(p)
            except re.error as exc:  # not a ValueError subclass, so main() would not catch it
                raise ValueError(f"evidence_patterns: bad regex {p!r}: {exc}") from exc
        return cfg

    def risky_hits(self, body: str) -> List[str]:
        """The risky-path patterns an issue body cites. A pattern is matched as a literal substring;
        a `*` inside it matches any run of path characters."""
        hits = []
        for pat in self.risky_paths:
            rx = re.escape(pat).replace(r"\*", r"[\w./-]*")
            if re.search(rx, body or ""):
                hits.append(pat)
        return sorted(set(hits))


@dataclass
class Context:
    """Everything classification needs besides the issue itself. Callables so the real run fetches
    lazily from GitHub and the tests inject dicts."""

    issue_body: Callable[[int], Optional[str]]
    pr_issue: Callable[[int], Optional[int]]
    config: Config = field(default_factory=Config)
    in_progress: Set[int] = field(default_factory=set)
    blocked_by: Dict[int, List[int]] = field(default_factory=dict)
    issue_title: Callable[[int], Optional[str]] = lambda n: None
    # The latest design note's `createdAt` on a root (ISO 8601), True when noted at an unknown time.
    design_noted: Callable[[int], object] = lambda n: False
    on_main: Callable[[int], List[str]] = lambda n: []
    today: date = field(default_factory=lambda: datetime.now().astimezone().date())


def pr_issue(pr: dict) -> Optional[int]:
    """The issue a PR works on: closing refs, else the branch name, else the body."""
    refs = pr.get("closingIssuesReferences") or []
    if refs:
        return int(refs[0]["number"])
    m = BRANCH_ISSUE.match(pr.get("headRefName") or "")
    if m:
        return int(m.group(1))
    m = BODY_ISSUE.search(pr.get("body") or "")
    return int(m.group(1)) if m else None


def chain_depth(number: int, body: str, ctx: Context, limit: int = 10) -> Tuple[int, int]:
    """Follow `Found by /review-loop on PR #M` footers back to the root issue.

    Returns (depth, root). Depth 0: not loop-filed. Depth 1: filed on a PR whose own issue has no
    footer. A hop whose PR or issue can't be resolved, or a cycle, ends the walk there."""
    depth, current, current_body = 0, number, body
    seen = {number}
    while depth < limit:
        m = FOOTER.search(current_body or "")
        if not m:
            return depth, current
        parent = ctx.pr_issue(int(m.group(1)))
        depth += 1
        if parent is None or parent in seen:
            return depth, current
        seen.add(parent)
        current = parent
        current_body = ctx.issue_body(parent) or ""
    return depth, current


def has_acceptance_criteria(body: str) -> bool:
    m = CRITERIA_HEADING.search(body or "")
    return bool(m) and bool(CHECKBOX.search(body[m.end():]))


def in_progress_numbers(worktree_porcelain: str, open_prs: List[dict]) -> Set[int]:
    """Issue numbers another session already owns: a worktree directory or branch name carrying the
    number, or an open PR whose issue resolves to it. Whole tokens only, so `12-15` yields both and
    `1215` yields neither of 12 or 15."""
    numbers: Set[int] = set()
    for line in worktree_porcelain.splitlines():
        if line.startswith("worktree "):
            numbers.update(int(n) for n in NUMBER_TOKEN.findall(line.split("/")[-1]))
        elif line.startswith("branch "):
            numbers.update(int(n) for n in NUMBER_TOKEN.findall(line.rsplit("/", 1)[-1]))
    for pr in open_prs:
        n = pr_issue(pr)
        if n is not None:
            numbers.add(n)
        numbers.update(int(r["number"]) for r in pr.get("closingIssuesReferences") or [])
        numbers.update(int(x) for x in NUMBER_TOKEN.findall((pr.get("headRefName") or "").split("/")[-1]))
    return numbers


def is_high_risky(issue: Issue, ctx: Context) -> bool:
    return "priority:high" in issue.labels and bool(ctx.config.risky_hits(issue.body))


def classify(issue: Issue, ctx: Context) -> Verdict:
    labels = set(issue.labels)
    skip = sorted(labels & set(ctx.config.skip_labels))
    if skip:
        return Verdict("skipped", "skip label: " + ", ".join(skip))
    parked = sorted(lb for lb in labels if lb.startswith("waiting:") or lb in PARKED_LABELS)
    if parked:
        return Verdict("parked", ", ".join(parked))
    if "epic" in labels:
        return Verdict("epic", "epic")
    if "review:ledger" in labels:
        return Verdict("ledger", "review-loop ledger")
    if not any(t in labels for t in CODE_FIX_TYPES):
        other = sorted(lb for lb in labels if lb.startswith("type:"))
        return Verdict("not_code_fix", ", ".join(other) or "no type label")
    if issue.number in ctx.in_progress:
        return Verdict("in_progress", "a worktree or open PR already carries this number")
    depth, root = chain_depth(issue.number, issue.body, ctx)
    warning = None
    if depth > MAX_CHAIN_DEPTH and PATCH_SEPARATELY_LABEL not in labels:
        if not is_high_risky(issue, ctx):
            return Verdict("chain", f"chain depth {depth} from #{root}", root_issue=root, chain_depth=depth)
        warning = (f"chain depth {depth} from #{root}, kept because it is priority:high on a risky path; "
                   f"read #{root}'s design note first if it has one")
    if not has_acceptance_criteria(issue.body):
        return Verdict("no_criteria", "no acceptance-criteria checklist")
    return Verdict("eligible", "clear code fix", root_issue=root if depth else None, chain_depth=depth,
                   warning=warning)


def _parse_utc(s: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def age_days(created_at: str, today: date) -> Optional[int]:
    when = _parse_utc(created_at)
    if when is None:
        return None
    if when.tzinfo is not None:
        when = when.astimezone()
    return (today - when.date()).days


def filed_after(created_at: str, note_at: object) -> bool:
    """True when an issue's `createdAt` is later than a design note's. False when either is unknown."""
    if not isinstance(note_at, str) or not note_at or not created_at:
        return False
    a, b = _parse_utc(created_at), _parse_utc(note_at)
    if a is None or b is None or (a.tzinfo is None) != (b.tzinfo is None):
        return False
    return a > b


def why_now(issue: Issue, ctx: Context) -> dict:
    """The value signals the queue is ordered by. Each is a fact from the issue, never a score."""
    body = issue.body or ""
    labels = set(issue.labels)
    evidence = []
    if INTRODUCED_BY.search(body):
        evidence.append("Introduced by a PR")
    evidence += sorted(labels & set(ctx.config.evidence_labels))
    for pat in ctx.config.evidence_patterns:
        if re.search(pat, body):
            evidence.append(f"matches /{pat}/")
    due = None
    for line in body.splitlines():
        if not DUE_CUE.search(line) or NOT_DUE_CUE.search(line):
            continue
        for y, mo, d in ISO_DATE.findall(line):
            try:
                when = date(int(y), int(mo), int(d))
            except ValueError:
                continue
            if (ctx.today - timedelta(days=OVERDUE_DAYS) <= when <= ctx.today + timedelta(days=DUE_DAYS)
                    and (due is None or when < due)):
                due = when
    note = None
    m = WHY_NOW_HEADING.search(body)
    if m:
        kept, fenced = [], False
        for line in body[m.end():].splitlines():
            if line.lstrip().startswith("```"):
                fenced = not fenced
            elif not fenced and NEXT_HEADING.match(line):
                break
            kept.append(line)
        note = " ".join(" ".join(kept).split()) or None
    return {
        "risky_path": ctx.config.risky_hits(body),
        "evidence": evidence,
        "unblocks": sorted(ctx.blocked_by.get(issue.number, [])),
        "due": due.isoformat() if due else None,
        "files_cited": len(code_files(body)),
        "note": note,
    }


def tier(why: dict) -> int:
    if why["due"]:
        return 0
    if why["risky_path"] and why["evidence"]:
        return 1
    if why["risky_path"] or why["evidence"] or why["unblocks"]:
        return 2
    return 3


def is_low_value(issue: Issue, v: Verdict, why: dict) -> bool:
    """The value floor: loop-filed (chain depth exactly 1), highest priority label `priority:low`, tier 3,
    without `sprint:keep` or a `## Why now` note."""
    labels = set(issue.labels)
    return (v.chain_depth == 1 and "priority:low" in labels
            and not labels & {"priority:high", "priority:medium"} and KEEP_LABEL not in labels
            and not why["note"] and tier(why) == 3)


def order_eligible(issues: List[Issue], whys: Optional[Dict[int, dict]] = None) -> List[Issue]:
    whys = whys or {}
    blank = {"due": None, "risky_path": [], "evidence": [], "unblocks": [], "files_cited": 0}

    def key(issue: Issue):
        labels = set(issue.labels)
        why = whys.get(issue.number) or blank
        prio = min((PRIORITY_RANK[p] for p in PRIORITY_RANK if p in labels), default=3)
        typ = min((TYPE_RANK[t] for t in TYPE_RANK if t in labels), default=3)
        return tier(why), why["due"] or "", prio, typ, why["files_cited"], issue.number

    return sorted(issues, key=key)


def code_files(body: str) -> Set[str]:
    """Code files an issue cites, as written. Tests and docs/config files are left out: two issues that
    both cite a test helper or the README don't touch the same code."""
    out = set()
    for token in FILE_TOKEN.findall(body or ""):
        while token.startswith("./"):
            token = token[2:]
        name = token.rsplit("/", 1)[-1]
        lower = name.lower()
        if (lower.startswith("test_") or ".test." in lower or ".spec." in lower or lower == "conftest.py"
                or token.startswith(("tests/", "test/")) or "/tests/" in token or "/__tests__/" in token):
            continue
        out.add(token)
    return out


def shared_files(a: Set[str], b: Set[str]) -> Set[str]:
    """Files two citation sets have in common. Two full paths must be equal; a bare name matches any path
    ending in it."""
    out = set()
    for x in a:
        for y in b:
            if x == y:
                out.add(x)
            elif ("/" not in x or "/" not in y) and x.rsplit("/", 1)[-1] == y.rsplit("/", 1)[-1]:
                out.add(max(x, y, key=len))
    return out


def bundle_candidates(issues: List[Issue]) -> List[dict]:
    """Groups of 2..MAX_BUNDLE issues citing a code file in common, greedy from the front of the queue."""
    files = {i.number: code_files(i.body) for i in issues}
    taken: Set[int] = set()
    out = []
    for lead in issues:
        if lead.number in taken or not files[lead.number]:
            continue
        members, shared = [lead.number], set()
        for other in issues:
            if len(members) == MAX_BUNDLE:
                break
            if other.number in taken or other.number in members:
                continue
            common = shared_files(files[lead.number], files[other.number])
            if common:
                members.append(other.number)
                shared |= common
        if len(members) > 1:
            taken.update(members)
            out.append({"lead": lead.number, "members": members, "files": sorted(shared)})
    return out


def mentions_by_number(log: str) -> Dict[int, List[str]]:
    """{issue number: ["<sha> <subject>", ...]} from `git log --format=%h%x1f%s%x1f%b%x1e`."""
    out: Dict[int, List[str]] = {}
    for record in log.split("\x1e"):
        parts = record.strip("\n").split("\x1f")
        if len(parts) < 2 or not parts[0].strip():
            continue
        sha, subject = parts[0].strip(), parts[1].strip()
        body = parts[2] if len(parts) > 2 else ""
        for n in sorted({int(m) for m in MENTION.findall(subject + "\n" + body)}):
            out.setdefault(n, []).append(f"{sha} {subject}")
    return out


def parse_ledger(comment_bodies: List[str]) -> List[dict]:
    """Unchecked ledger lines from the ledger issue's comments (each headed `### PR #N`; a bold `**path**`
    line names the file for the lines under it)."""
    out = []
    for body in comment_bodies:
        pr, heading_path = None, ""
        for raw in (body or "").splitlines():
            m = LEDGER_PR.match(raw)
            if m:
                pr, heading_path = int(m.group(1)), ""
                continue
            m = LEDGER_FILE.match(raw.strip())
            if m:
                heading_path = m.group(1).strip()
                continue
            m = LEDGER_ENTRY.match(raw)
            if not m or m.group("mark") != " ":
                continue
            out.append({"pr": pr, "path": m.group("path") or heading_path, "line": int(m.group("line")),
                        "category": m.group("cat"), "text": " ".join(m.group("text").split())})
    return out


def ledger_sweep(entries: List[dict], issues: List[Issue]) -> dict:
    by_issue = {}
    for issue in issues:
        names = {f.rsplit("/", 1)[-1] for f in code_files(issue.body)}
        hits = [e for e in entries if e["path"] and e["path"].rsplit("/", 1)[-1] in names
                and not LEDGER_UNREACHABLE.search(e["text"])]
        if hits:
            by_issue[str(issue.number)] = hits
    return {"total": len(entries), "prs": len({e["pr"] for e in entries if e["pr"]}), "by_issue": by_issue}


def design_outcomes(chains: Dict[str, List[int]], ctx: Context, open_numbers: Set[int],
                    notes: Optional[Dict[int, object]] = None,
                    kept_eligible: Optional[Dict[str, List[int]]] = None) -> Dict[int, str]:
    """Each root with skipped follow-ups -> "noted" (a design note is already posted), else, with
    MIN_DESIGN_FOLLOWUPS or more, "busy" (an open root another session owns) or "pass"."""
    out = {}
    for root, numbers in chains.items():
        if not numbers:
            continue
        r = int(root)
        noted = notes[r] if notes is not None and r in notes else ctx.design_noted(r)
        if noted:
            out[r] = "noted"
        elif len(numbers) + len((kept_eligible or {}).get(root, ())) < MIN_DESIGN_FOLLOWUPS:
            continue
        elif r in open_numbers and r in ctx.in_progress:
            out[r] = "busy"
        else:
            out[r] = "pass"
    return out


def design_passes(chains: Dict[str, List[int]], ctx: Context, outcomes: Dict[int, str],
                  kept_eligible: Optional[Dict[str, List[int]]] = None) -> List[dict]:
    items = [{"root": r, "title": ctx.issue_title(r), "follow_ups": sorted(chains[str(r)]),
              "eligible_follow_ups": sorted((kept_eligible or {}).get(str(r), ()))}
             for r, o in outcomes.items() if o == "pass"]
    return sorted(items, key=lambda i: (-len(i["follow_ups"]), i["root"]))


def _owner_vouched(issue: Issue, why: dict) -> bool:
    return bool(why["note"]) or "priority:high" in issue.labels


def _row(issue: Issue, v: Verdict) -> dict:
    return {"number": issue.number, "title": issue.title,
            "labels": [lb for lb in issue.labels if lb != "backlog"], "reason": v.reason,
            "root_issue": v.root_issue, "chain_depth": v.chain_depth, "warning": v.warning}


def triage(issues: List[Issue], ctx: Context) -> dict:
    groups: Dict[str, List[dict]] = {}
    eligible: List[Issue] = []
    verdicts: Dict[int, Verdict] = {}
    for issue in issues:
        v = classify(issue, ctx)
        verdicts[issue.number] = v
        if v.group == "eligible":
            eligible.append(issue)
        else:
            groups.setdefault(v.group, []).append(_row(issue, v))
    by_number = {i.number: i for i in issues}
    chain_rows = groups.get("chain", [])
    notes = {r: ctx.design_noted(r) for r in sorted({row["root_issue"] for row in chain_rows})}
    late, kept = [], []
    for row in chain_rows:
        created = by_number[row["number"]].created_at
        row["created_at"] = created or None
        row["age_days"] = age_days(created, ctx.today)
        note_at = notes.get(row["root_issue"])
        if filed_after(created, note_at):
            late.append(dict(row, note_at=note_at, choices=list(LATE_CHOICES)))
        else:
            kept.append(row)
    if chain_rows:
        groups["chain"] = kept
    chains: Dict[str, List[int]] = {}
    for row in kept:
        chains.setdefault(str(row["root_issue"]), []).append(row["number"])
    ages = {str(row["number"]): row["age_days"] for row in kept if row["age_days"] is not None}
    kept_eligible: Dict[str, List[int]] = {}
    for i in eligible:
        if verdicts[i.number].warning:
            kept_eligible.setdefault(str(verdicts[i.number].root_issue), []).append(i.number)
    outcomes = design_outcomes(chains, ctx, {i.number for i in issues}, notes, kept_eligible)
    passes = design_passes(chains, ctx, outcomes, kept_eligible)
    roots = {p["root"] for p in passes}
    eligible_numbers = {i.number for i in eligible}
    for p in passes:  # an open root is worked after its design note, not queued twice
        p["root_open"] = p["root"] in eligible_numbers
    eligible = [i for i in eligible if i.number not in roots]
    whys = {i.number: why_now(i, ctx) for i in eligible}
    low = [i for i in eligible if is_low_value(i, verdicts[i.number], whys[i.number])]
    if low:
        rows = []
        for i in low:
            v = verdicts[i.number]
            rows.append(dict(_row(i, Verdict("low_value", "loop-filed, priority:low, tier 3",
                                             root_issue=v.root_issue, chain_depth=v.chain_depth)),
                             age_days=age_days(i.created_at, ctx.today)))
        rows.sort(key=lambda r: (r["age_days"] is None, -(r["age_days"] or 0), r["number"]))
        groups["low_value"] = rows
        eligible = [i for i in eligible if i not in low]
    ordered = order_eligible(eligible, whys)
    groups["eligible"] = [dict(_row(i, verdicts[i.number]), why=whys[i.number], tier=tier(whys[i.number]))
                          for i in ordered]
    chained = {n for numbers in chains.values() for n in numbers} | {r["number"] for r in late}
    floored = {i.number for i in low}
    on_main = {}
    for n in sorted({i.number for i in ordered} | chained | floored):
        hits = ctx.on_main(n)
        if hits:
            on_main[str(n)] = hits
    return {"groups": groups, "chains": chains, "chain_ages": ages, "late_follow_ups": late,
            "design_passes": passes,
            "design_noted_roots": sorted(r for r, o in outcomes.items() if o == "noted"),
            "design_busy_roots": sorted(r for r, o in outcomes.items() if o == "busy"),
            "bundles": bundle_candidates(ordered), "on_main": on_main, "open_issues": len(issues),
            "tier3_only": (bool(eligible) and not passes and not late
                           and all(tier(whys[i.number]) == 3 and not _owner_vouched(i, whys[i.number])
                                   for i in eligible))}


def _why_line(row: dict) -> str:
    why = row.get("why") or {}
    parts = [f"tier {row.get('tier', 3)}"]
    if why.get("due"):
        parts.append(f"due {why['due']}")
    if why.get("risky_path"):
        parts.append("risky path (" + ", ".join(why["risky_path"]) + ")")
    if why.get("evidence"):
        parts.append("evidence: " + ", ".join(why["evidence"]))
    if why.get("unblocks"):
        parts.append("unblocks " + ", ".join(f"#{n}" for n in why["unblocks"]))
    parts.append(f"files cited: {why.get('files_cited', 0)}")
    if why.get("note"):
        parts.append(f"owner: {why['note']}")
    return "; ".join(parts)


def render(result: dict) -> str:
    groups = result["groups"]
    out = [f"Open issues: {result['open_issues']}"]
    passes = result.get("design_passes") or []
    if passes:
        out += ["", f"## Design passes ({len(passes)}), recommended first: one note on the root retires its follow-ups", ""]
        for item in passes:
            title = f" {item['title']}" if item.get("title") else ""
            line = f"- #{item['root']}{title}: " + ", ".join(f"#{n}" for n in item["follow_ups"])
            if item.get("eligible_follow_ups"):
                line += (" (also read " + ", ".join(f"#{n}" for n in item["eligible_follow_ups"])
                         + ", queued separately: context, not in the plan)")
            if item.get("root_open"):
                line += " (the root is itself an open code fix: queue it by number after the note)"
            out.append(line)
    out += ["", f"## Eligible ({len(groups['eligible'])}), in queue order "
            "(tier 0 due, 1 risky path + evidence, 2 one signal, 3 rest)", ""]
    if result.get("tier3_only"):
        out += ["STOP: every eligible issue is tier 3 (no due date, risky path, evidence or unblocks) and there "
                "is no design pass. Recommend an empty queue; name items only if one is worth a PR anyway.", ""]
    for row in groups["eligible"]:
        chain = ""
        if row["chain_depth"] and row["root_issue"] not in (None, row["number"]):
            chain = f" (chain depth {row['chain_depth']} from #{row['root_issue']})"
            if row.get("warning"):
                chain = f" (WARNING: {row['warning']})"
            elif row["chain_depth"] > MAX_CHAIN_DEPTH:
                chain = chain[:-1] + f", cleared by {PATCH_SEPARATELY_LABEL})"
        elif row["chain_depth"]:
            chain = " (loop-filed; its PR resolves to no other issue)"
        out.append(f"- #{row['number']} [{', '.join(row['labels'])}] {row['title']}{chain}")
        out.append("  why now: " + _why_line(row))
    bundles = result.get("bundles") or []
    if bundles:
        out += ["", f"## Bundle candidates ({len(bundles)}): one PR can close the whole group (at most {MAX_BUNDLE})", ""]
        for b in bundles:
            out.append(f"- #{b['lead']} + " + ", ".join(f"#{n}" for n in b["members"][1:])
                       + " (shared: " + ", ".join(b["files"]) + ")")
    sweep = result.get("ledger") or {}
    if sweep.get("by_issue"):
        out += ["", f"## Ledger sweep: {sweep['total']} unchecked lines from {sweep['prs']} PRs; "
                f"{len(sweep['by_issue'])} eligible issues have lines on their files. Promote one only if it "
                "describes a failure that has happened, or fold it into the issue's PR", ""]
        for n, hits in sorted(sweep["by_issue"].items(), key=lambda kv: int(kv[0])):
            shown = hits[:MAX_LEDGER_SHOWN]
            more = f" (+{len(hits) - len(shown)} more)" if len(hits) > len(shown) else ""
            out.append(f"- #{n}{more}:")
            out += [f"  - PR #{e['pr']} {e['path']}:{e['line']} [{e['category']}] {e['text'][:160]}" for e in shown]
    seen = result.get("on_main") or {}
    if seen:
        out += ["", f"## May already be fixed ({len(seen)}): the number appears in a commit on the default "
                "branch. Read the commit before queueing", ""]
        for n, hits in sorted(seen.items(), key=lambda kv: int(kv[0])):
            shown = hits[:MAX_MENTIONS_SHOWN]
            more = f" (+{len(hits) - len(shown)} more)" if len(hits) > len(shown) else ""
            out.append(f"- #{n}: " + "; ".join(shown) + more)
    low = groups.get("low_value") or []
    if low:
        out += ["", f"## Low value, not queued ({len(low)}): loop-filed, priority:low, no due date, risky path, "
                f"evidence or unblocks. Close as not worth it, or raise the priority / add {KEEP_LABEL}", ""]
        for row in low:
            age = f", {row['age_days']}d old" if row.get("age_days") is not None else ""
            root = (f"root #{row['root_issue']}" if row["root_issue"] not in (None, row["number"])
                    else "its PR resolves to no other issue")
            fixed = " [number appears on the default branch: read the commit]" if str(row["number"]) in seen else ""
            out.append(f"- #{row['number']} {row['title']} ({root}{age}){fixed}")
    late = result.get("late_follow_ups") or []
    if late:
        out += ["", f"## Filed after the root's design note ({len(late)}): choose one per issue: "
                + " / ".join(LATE_CHOICES), ""]
        for row in late:
            age = f", {row['age_days']}d old" if row.get("age_days") is not None else ""
            out.append(f"- #{row['number']} [{', '.join(row['labels'])}] {row['title']} (root #{row['root_issue']}, "
                       f"note {str(row['note_at'])[:10]}, filed {str(row['created_at'])[:10]}{age})")
    ages = result.get("chain_ages") or {}
    if result["chains"]:
        out += ["", "## Chain issues skipped (depth >= 2), per root issue", ""]
        pass_roots = {p["root"] for p in passes}
        noted = set(result.get("design_noted_roots") or ())
        busy = set(result.get("design_busy_roots") or ())
        for root, numbers in sorted(result["chains"].items(), key=lambda kv: int(kv[0])):
            tag = ""
            if int(root) in pass_roots:
                tag = " (design pass above)"
            elif int(root) in noted:
                tag = (" (design note already posted: read it first; one it says to patch on its own: add "
                       f"{PATCH_SEPARATELY_LABEL})")
            elif int(root) in busy:
                tag = " (open root in progress elsewhere)"
            out.append(f"- #{root}{tag}: " + ", ".join(
                f"#{n}" + (f" ({ages[str(n)]}d)" if str(n) in ages else "") for n in numbers))
    for group, title in (
        ("in_progress", "In progress elsewhere"),
        ("no_criteria", "No acceptance criteria"),
        ("not_code_fix", "Not a code fix (features, untyped)"),
        ("skipped", "Skipped by config"),
        ("parked", "Parked"),
        ("epic", "Epics"),
        ("ledger", "Ledger"),
    ):
        rows = groups.get(group)
        if rows:
            out += ["", f"## {title} ({len(rows)})", ""]
            out += [f"- #{r['number']} {r['title']} — {r['reason']}" for r in rows]
    return "\n".join(out) + "\n"


# --- GitHub-backed run --------------------------------------------------------


def _gh_json(args: List[str]):
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return json.loads(result.stdout or "null")


def _git(repo: str, *args: str) -> str:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True).stdout


def _fetch_open_issues(limit: int) -> List[Issue]:
    rows = _gh_json(["issue", "list", "--state", "open", "--limit", str(limit),
                     "--json", "number,title,labels,body,createdAt"])
    if len(rows) >= limit:
        print(f"warning: gh returned {limit} issues; the list may be cut off", file=sys.stderr)
    return [Issue(r["number"], r["title"], r.get("body") or "", tuple(lb["name"] for lb in r["labels"]),
                  r.get("createdAt") or "") for r in rows]


def blocked_by_map(parked: Dict[int, List[str]]) -> Dict[int, List[int]]:
    """{blocking issue: [parked issues waiting on it]}; the latest `Parked:` line per issue wins."""
    out: Dict[int, List[int]] = {}
    for number, comments in parked.items():
        target = None
        for body in comments:
            m = PARKED_ON.search(body or "")
            if m:
                target = int(m.group(1))
        if target is not None:
            out.setdefault(target, []).append(number)
    return out


def _default_ref(repo: str) -> str:
    try:
        return _git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip() or "origin/main"
    except (subprocess.CalledProcessError, OSError):
        return "origin/main"


def _main_mentions(repo: str) -> Dict[int, List[str]]:
    try:
        log = _git(repo, "log", _default_ref(repo), "-n", "400", "--format=%h%x1f%s%x1f%b%x1e")
    except (subprocess.CalledProcessError, OSError):
        return {}
    return mentions_by_number(log)


def _ledger_comments(number: int) -> List[str]:
    try:
        res = subprocess.run(["gh", "api", f"repos/{{owner}}/{{repo}}/issues/{number}/comments", "--paginate",
                              "--jq", ".[] | .body | @json"], capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, OSError):
        return []
    bodies = []
    for line in res.stdout.splitlines():
        try:
            bodies.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return bodies


def _live_context(issues: List[Issue], repo: str, config: Config) -> Context:
    bodies: Dict[int, Optional[str]] = {i.number: i.body for i in issues}
    titles: Dict[int, Optional[str]] = {i.number: i.title for i in issues}
    prs: Dict[int, Optional[int]] = {}

    def issue_body(n: int) -> Optional[str]:
        if n not in bodies:
            try:
                bodies[n] = (_gh_json(["issue", "view", str(n), "--json", "body"]) or {}).get("body") or ""
            except subprocess.CalledProcessError:
                bodies[n] = None
        return bodies[n]

    def pr_issue_live(m: int) -> Optional[int]:
        if m not in prs:
            try:
                prs[m] = pr_issue(_gh_json(["pr", "view", str(m), "--json",
                                            "closingIssuesReferences,headRefName,body"]) or {})
            except subprocess.CalledProcessError:
                prs[m] = None
        return prs[m]

    def issue_title(n: int) -> Optional[str]:
        if n not in titles:
            try:
                titles[n] = (_gh_json(["issue", "view", str(n), "--json", "title"]) or {}).get("title")
            except subprocess.CalledProcessError:
                titles[n] = None
        return titles[n]

    def design_noted(n: int) -> object:
        try:
            rows = (_gh_json(["issue", "view", str(n), "--json", "comments"]) or {}).get("comments") or []
        except subprocess.CalledProcessError:
            return False
        times = [c.get("createdAt") or "" for c in rows if DESIGN_NOTE.search(c.get("body") or "")]
        if not times:
            return False
        return max(times) or True

    mentions = _main_mentions(repo)
    porcelain = _git(repo, "worktree", "list", "--porcelain")
    open_prs = _gh_json(["pr", "list", "--state", "open", "--limit", "200",
                         "--json", "number,headRefName,body,closingIssuesReferences"]) or []
    parked: Dict[int, List[str]] = {}
    for issue in issues:
        if "waiting:issue" in issue.labels:
            try:
                rows = (_gh_json(["issue", "view", str(issue.number), "--json", "comments"]) or {}).get("comments") or []
            except subprocess.CalledProcessError:
                continue
            parked[issue.number] = [c.get("body") or "" for c in rows]
    return Context(issue_body, pr_issue_live, config=config, in_progress=in_progress_numbers(porcelain, open_prs),
                   blocked_by=blocked_by_map(parked), issue_title=issue_title, design_noted=design_noted,
                   on_main=lambda n: mentions.get(n, []))


def load_config(path: Optional[str], repo: str) -> Config:
    explicit = path is not None
    path = path or f"{repo}/.claude/review-loop.json"
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        if explicit:
            raise
        return Config()
    if not isinstance(raw, dict):
        raise ValueError("config must be a JSON object")
    return Config.from_dict(raw)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--out", help="also write the groups as JSON to this file")
    parser.add_argument("--repo", default=".", help="main repository path (for `git worktree list` and config)")
    parser.add_argument("--config", default=None, help="default: <repo>/.claude/review-loop.json if present")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config, args.repo)
    except (OSError, ValueError) as exc:
        print(f"error: config: {exc}", file=sys.stderr)
        return 2
    try:
        issues = _fetch_open_issues(args.limit)
        result = triage(issues, _live_context(issues, args.repo, config))
    except (subprocess.CalledProcessError, OSError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        print(f"error: {detail.strip()}", file=sys.stderr)
        return 2
    ledger_rows = result["groups"].get("ledger") or []
    if ledger_rows:
        eligible_numbers = {r["number"] for r in result["groups"]["eligible"]}
        result["ledger"] = ledger_sweep(parse_ledger(_ledger_comments(ledger_rows[0]["number"])),
                                        [i for i in issues if i.number in eligible_numbers])
    sys.stdout.write(render(result))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
