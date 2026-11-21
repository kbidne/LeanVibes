"""Tests for backlog_sprint_triage.py. Run: python3 -m unittest discover -s claude-code/.claude/scripts"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import backlog_sprint_triage as t  # noqa: E402

CRITERIA = "\n## Acceptance Criteria\n- [ ] it works\n"
TODAY = date(2026, 6, 15)


def issue(n, body="", labels=("type:bug", "priority:medium"), created="2026-06-01T12:00:00Z", title=None):
    return t.Issue(n, title or f"issue {n}", body, tuple(labels), created)


def footer(pr):
    return f"\n\nFound by /review-loop on PR #{pr}, round 1: src/x.py#L3\n"


def ctx(bodies=None, prs=None, config=None, **kw):
    bodies = bodies or {}
    prs = prs or {}
    return t.Context(issue_body=lambda n: bodies.get(n), pr_issue=lambda m: prs.get(m),
                     config=config or t.Config(), today=TODAY, **kw)


class ChainDepthTests(unittest.TestCase):
    def test_not_loop_filed(self):
        self.assertEqual(t.chain_depth(5, "plain", ctx()), (0, 5))

    def test_depth_one_and_two(self):
        # #10 (root, no footer) -> PR 11 -> #12 (depth 1) -> PR 13 -> #14 (depth 2)
        c = ctx(bodies={10: "root", 12: "x" + footer(11)}, prs={11: 10, 13: 12})
        self.assertEqual(t.chain_depth(12, "x" + footer(11), c), (1, 10))
        self.assertEqual(t.chain_depth(14, "y" + footer(13), c), (2, 10))

    def test_cycle_stops(self):
        c = ctx(bodies={20: "a" + footer(21)}, prs={21: 20})
        depth, _ = t.chain_depth(20, "a" + footer(21), c)
        self.assertEqual(depth, 1)


class ClassifyTests(unittest.TestCase):
    def test_groups_in_order(self):
        c = ctx(config=t.Config(skip_labels=["wontfix-here"]))
        cases = [
            (issue(1, CRITERIA, ("type:bug", "wontfix-here", "waiting:date")), "skipped"),
            (issue(2, CRITERIA, ("type:bug", "waiting:date", "epic")), "parked"),
            (issue(3, CRITERIA, ("type:bug", "stays open")), "parked"),
            (issue(4, CRITERIA, ("type:bug", "epic")), "epic"),
            (issue(5, CRITERIA, ("review:ledger", "stays open")), "parked"),
            (issue(6, CRITERIA, ("review:ledger", "type:debt")), "ledger"),
            (issue(7, CRITERIA, ("type:feature",)), "not_code_fix"),
            (issue(8, "no checklist", ("type:bug",)), "no_criteria"),
            (issue(9, CRITERIA, ("type:enhancement",)), "eligible"),
        ]
        for i, group in cases:
            self.assertEqual(t.classify(i, c).group, group, i.number)

    def test_in_progress(self):
        c = ctx(in_progress={9})
        self.assertEqual(t.classify(issue(9, CRITERIA), c).group, "in_progress")

    def test_depth_two_is_chain_unless_cleared(self):
        c = ctx(bodies={10: "root", 12: "x" + footer(11)}, prs={11: 10, 13: 12})
        body = CRITERIA + footer(13)
        self.assertEqual(t.classify(issue(14, body), c).group, "chain")
        cleared = issue(14, body, ("type:bug", "design:patch-separately"))
        self.assertEqual(t.classify(cleared, c).group, "eligible")

    def test_high_priority_risky_follow_up_stays_eligible_with_warning(self):
        c = ctx(bodies={10: "root", 12: "x" + footer(11)}, prs={11: 10, 13: 12},
                config=t.Config(risky_paths=["src/payments/"]))
        body = "breaks src/payments/charge.py" + CRITERIA + footer(13)
        v = t.classify(issue(14, body, ("type:bug", "priority:high")), c)
        self.assertEqual(v.group, "eligible")
        self.assertIn("read #10", v.warning)


class WhyNowTests(unittest.TestCase):
    def test_due_window(self):
        c = ctx()
        self.assertEqual(t.why_now(issue(1, "Deadline: 2026-06-20"), c)["due"], "2026-06-20")
        self.assertIsNone(t.why_now(issue(1, "Deadline: 2026-08-20"), c)["due"])  # too far ahead
        self.assertIsNone(t.why_now(issue(1, "Not before 2026-06-20"), c)["due"])
        self.assertIsNone(t.why_now(issue(1, "Fails due to a race on 2026-06-20"), c)["due"])

    def test_evidence_sources(self):
        c = ctx(config=t.Config(evidence_labels=["incident"], evidence_patterns=[r"Sentry-\d+"]))
        why = t.why_now(issue(1, "Introduced by: PR #4\nSee Sentry-123", ("type:bug", "incident")), c)
        self.assertEqual(why["evidence"], ["Introduced by a PR", "incident", r"matches /Sentry-\d+/"])

    def test_why_now_note_stops_at_next_heading(self):
        body = "## Why now\nBlocks the\n  release.\n## Acceptance Criteria\n- [ ] x"
        self.assertEqual(t.why_now(issue(1, body), ctx())["note"], "Blocks the release.")

    def test_tiers(self):
        cfg = t.Config(risky_paths=["src/auth/"])
        c = ctx(config=cfg, blocked_by={3: [99]})
        self.assertEqual(t.tier(t.why_now(issue(1, "due 2026-06-16"), c)), 0)
        self.assertEqual(t.tier(t.why_now(issue(2, "src/auth/x.py\nIntroduced by: PR #1"), c)), 1)
        self.assertEqual(t.tier(t.why_now(issue(3, "plain"), c)), 2)
        self.assertEqual(t.tier(t.why_now(issue(4, "plain"), c)), 3)

    def test_risky_glob(self):
        cfg = t.Config(risky_paths=["services/*/billing"])
        self.assertEqual(cfg.risky_hits("see services/api/billing.py"), ["services/*/billing"])


class OrderTests(unittest.TestCase):
    def test_tier_then_priority_then_type_then_files(self):
        c = ctx()
        a = issue(1, "plain", ("type:enhancement", "priority:high"))
        b = issue(2, "plain", ("type:bug", "priority:high"))
        d = issue(3, "due 2026-06-16", ("type:debt", "priority:low"))
        e = issue(4, "src/a.py src/b.py", ("type:bug", "priority:high"))
        whys = {i.number: t.why_now(i, c) for i in (a, b, d, e)}
        self.assertEqual([i.number for i in t.order_eligible([a, b, d, e], whys)], [3, 2, 4, 1])


class FilesAndBundleTests(unittest.TestCase):
    def test_code_files_skip_tests_docs_and_prose(self):
        files = t.code_files("src/a.py, e.g. github.com, tests/test_a.py web/app.test.ts docs/x.md ./b.sh")
        self.assertEqual(files, {"src/a.py", "b.sh"})

    def test_bundles_by_shared_file(self):
        issues = [issue(1, "src/a.py"), issue(2, "src/b.py"), issue(3, "a.py"), issue(4, "src/a.py"),
                  issue(5, "src/a.py")]
        bundles = t.bundle_candidates(issues)
        self.assertEqual(bundles, [{"lead": 1, "members": [1, 3, 4], "files": ["src/a.py"]}])

    def test_two_different_full_paths_do_not_bundle(self):
        self.assertEqual(t.bundle_candidates([issue(1, "a/events.py"), issue(2, "b/events.py")]), [])


class InProgressTests(unittest.TestCase):
    def test_worktree_and_pr_numbers(self):
        porcelain = ("worktree /repo\nbranch refs/heads/main\n\n"
                     "worktree /repo/.claude/worktrees/12\nbranch refs/heads/fix/12-x\n\n"
                     "worktree /repo/.claude/worktrees/pr-30\nbranch refs/heads/fix/1215-y\n")
        prs = [{"closingIssuesReferences": [{"number": 40}], "headRefName": "feat/x", "body": ""},
               {"closingIssuesReferences": [], "headRefName": "fix/41-z", "body": ""}]
        nums = t.in_progress_numbers(porcelain, prs)
        self.assertTrue({12, 30, 1215, 40, 41} <= nums)
        self.assertNotIn(15, nums)


class LedgerTests(unittest.TestCase):
    def test_parse_and_sweep(self):
        body = ("### PR #7\n**src/a.py**\n- [ ] [style] src/a.py:3 — long line\n"
                "- [x] [style] src/a.py:4 — done\n- [ ] [correctness] :9 — no path of its own\n"
                "- [ ] [correctness] src/a.py:10 — guard missing — not reachable: no caller\n")
        entries = t.parse_ledger([body])
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[1]["path"], "src/a.py")  # took the heading's path
        sweep = t.ledger_sweep(entries, [issue(1, "fix src/a.py")])
        self.assertEqual(len(sweep["by_issue"]["1"]), 2)  # the not-reachable line is not listed
        self.assertEqual(sweep["total"], 3)


class TriageTests(unittest.TestCase):
    def test_design_pass_low_value_and_stop_rule(self):
        # root 10; PR 11 fixed it and filed 12 and 16 (depth 1); PR 13 fixed 12 and filed 14, 15 (depth 2)
        bodies = {10: "root" + CRITERIA, 12: "x" + footer(11)}
        prs = {11: 10, 13: 12}
        issues = [
            issue(10, "root" + CRITERIA),
            issue(12, "x" + CRITERIA + footer(11), ("type:bug", "priority:low")),
            issue(14, "a" + CRITERIA + footer(13)),
            issue(15, "b" + CRITERIA + footer(13)),
            issue(16, "c" + CRITERIA + footer(11), ("type:bug", "priority:low", "sprint:keep")),
        ]
        result = t.triage(issues, ctx(bodies=bodies, prs=prs))
        self.assertEqual([p["root"] for p in result["design_passes"]], [10])
        self.assertTrue(result["design_passes"][0]["root_open"])
        self.assertEqual(result["chains"], {"10": [14, 15]})
        self.assertEqual([r["number"] for r in result["groups"]["low_value"]], [12])
        self.assertEqual([r["number"] for r in result["groups"]["eligible"]], [16])
        self.assertFalse(result["tier3_only"])  # a design pass blocks the stop rule

    def test_stop_rule(self):
        result = t.triage([issue(1, "plain" + CRITERIA), issue(2, "plain" + CRITERIA)], ctx())
        self.assertTrue(result["tier3_only"])
        self.assertIn("STOP:", t.render(result))
        vouched = t.triage([issue(1, "plain" + CRITERIA, ("type:bug", "priority:high"))], ctx())
        self.assertFalse(vouched["tier3_only"])

    def test_noted_root_and_late_follow_up(self):
        bodies = {10: "root", 12: "x" + footer(11)}
        prs = {11: 10, 13: 12}
        issues = [issue(14, "a" + CRITERIA + footer(13), created="2026-05-01T00:00:00Z"),
                  issue(15, "b" + CRITERIA + footer(13), created="2026-06-10T00:00:00Z")]
        result = t.triage(issues, ctx(bodies=bodies, prs=prs, design_noted=lambda n: "2026-06-01T00:00:00Z"))
        self.assertEqual(result["design_passes"], [])
        self.assertEqual(result["design_noted_roots"], [10])
        self.assertEqual([r["number"] for r in result["late_follow_ups"]], [15])
        self.assertEqual(result["chains"], {"10": [14]})

    def test_render_smoke(self):
        result = t.triage([issue(1, "src/a.py due 2026-06-16" + CRITERIA), issue(2, "src/a.py" + CRITERIA)],
                          ctx(on_main=lambda n: ["abc123 fix #1"] if n == 1 else []))
        text = t.render(result)
        self.assertIn("## Eligible (2)", text)
        self.assertIn("## Bundle candidates (1)", text)
        self.assertIn("## May already be fixed (1)", text)


class ConfigTests(unittest.TestCase):
    def test_bad_config_raises(self):
        with self.assertRaises(ValueError):
            t.Config.from_dict({"risky_paths": "src/"})
        with self.assertRaises(ValueError):
            t.Config.from_dict({"sprint": {"evidence_patterns": ["("]}})

    def test_example_config_loads(self):
        path = Path(__file__).resolve().parents[1] / "review-loop.json.example"
        cfg = t.load_config(str(path), ".")
        self.assertTrue(cfg.risky_paths)


if __name__ == "__main__":
    unittest.main()
