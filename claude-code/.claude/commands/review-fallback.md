---
description: Review a PR for correctness bugs where the built-in /code-review is not available. Used by /review-loop as its fallback reviewer
argument-hint: <low|medium|high> <PR number>
---

# Review Fallback

A repo-owned stand-in for Claude Code's `/code-review`, for sessions where
that skill is not installed or is switched off (some cloud and web sessions).
`/review-loop` uses it only then, and records `reviewer: "fallback"` so these
reviews can be told apart in its metrics. **It is not `/code-review`.** Say so
in anything you post.

Run it in a **fresh Opus agent** that has not seen the PR author's reasoning.
A reviewer that inherits the author's account of the change reads the code to
confirm that account.

## Arguments

`$ARGUMENTS`: a level (`low`, `medium` or `high`, default `medium`), then the
PR number. Always return every finding: a capped review can look clean.

| Level | What runs |
|---|---|
| `low` | pass 1, keep only findings you are sure of |
| `medium` | passes 1 and 2, then pass 4 on every candidate |
| `high` | passes 1, 2 and 3, then pass 4 on every candidate |

## Instructions

Work from the PR branch's worktree. Post nothing to the PR: return the JSON at
the end and the caller posts it.

### 0. Load the PR

```bash
gh pr view <N> --json number,title,body,baseRefName,headRefOid,files,additions,deletions
git fetch -q origin <baseRefName>
git diff origin/<baseRefName>...<headRefOid>
```

If the head commit isn't checked out, check it out detached
(`git switch --detach <headRefOid>`) so what you read is what will merge. Read
the PR body and linked issue for what the change is meant to do, and nothing
that argues the change is correct.

### 1. Read for bugs

For every changed file, read the whole function around each hunk, not the
hunk alone, and read the callers and writers of anything whose contract
changed (`grep` the repo; don't assume). Look for:

- wrong results: off-by-one, wrong operator, inverted condition, an
  unreachable or missed branch, a value that is null, empty, zero or the
  wrong type in a real call;
- state and ordering: a write that can happen twice, check-then-act, a lock
  or transaction that doesn't cover what it should, a failure path that
  leaves partial state;
- error handling that swallows a failure or turns it into success;
- security: unescaped user input in HTML, SQL or shell; secrets in code or
  logs; a missing authorization check on a new route;
- the project's own written rules (CLAUDE.md, CONTRIBUTING, lint configs).
  Read the sections that match the paths touched.

A candidate needs a concrete failure scenario: inputs or state, then the
wrong output or crash. No scenario, no finding.

### 2. Read the tests

For each new or changed test: does it fail without the change it claims to
pin? Is it hermetic (no network, no files written into the checkout, no
dependence on the clock, the date or test order)? Code that branches on the
hour or date needs a fixed time in its fixtures, never `now - delta`. Does it
assert the specific mechanism, or only a general property? A test with
threads, event loops or timers must survive repeated runs under load.

### 3. Run it (`high` only)

For each new or changed function, find its real callers, then execute it in a
scratch script in a directory outside the checkout, with the values callers
pass and the boundary values around them: null, empty, zero, the largest the
column or API allows, the types callers really build. Where the change is a
script, run it, including its failure paths (missing file, stale lock, a kill
at each step), with stubs for anything shared: never touch a real lock, log
or database other sessions use. Compare against the base branch when the
claim is "this used to work". Hostile inputs no caller builds are worth
running only at a trust boundary (request bodies, third-party payloads,
user-edited config). Report what you ran.

Write each scratch script to a file with the Write tool (it creates the
directory; don't `mkdir` it) and run it as one command
(`<interpreter> /tmp/review-scratch/check_x.py`, with the import path set
inside the script). Unattended runs deny `mkdir` outside the project,
`cd <dir> && ...` and multi-line `-c` strings.

### 4. Try to disprove each candidate

For every candidate, make one honest attempt to show it is wrong: find the
upstream guard that prevents the scenario, or the test that already pins the
correct behaviour. Drop it only if that attempt succeeds. Then look for what
produces the scenario today and set `reachable_via` to its `file:line`, or
`null` if you found none. Finding no caller does not drop a candidate: report
it with `reachable_via: null`, and the loop sends it to the ledger. Neither
does "it was already wrong before this PR" when the bug sits in a line the
diff touches. When the trigger is an event
rather than a caller (a crash, a timeout, a signal), cite the code running
when it happens and put the trigger in `evidence`. A scenario you reproduced
counts as reachable.

You don't decide what blocks a merge: the loop's fixer does, from `category`
and `reachable_via`. Report only findings in the blocking categories
(`correctness`, `test`, `test-coverage`, `security`, `conventions` for a
written project rule or a CI gate). Style, naming and "could be simpler" are
not findings here.

### 5. Return

JSON only:

```json
{"findings": [
  {"path": "src/x.py", "line": 41, "category": "correctness|test|test-coverage|security|conventions",
   "summary": "one sentence", "failure_scenario": "inputs or state -> wrong output or crash",
   "reachable_via": "src/y.py:88", "evidence": "what you ran or read that shows it"}
], "ran": ["scratch scripts or commands you executed"], "reviewer": "fallback"}
```

`line` is a line in the PR's diff. An empty review is
`{"findings": [], "ran": [...], "reviewer": "fallback"}`: list what you ran so
a reader can tell it from a review that never looked.
