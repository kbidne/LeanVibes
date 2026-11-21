"""Tests for workflow_state.py. Run: python3 -m unittest discover -s claude-code/.claude/scripts"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow_state as ws  # noqa: E402


def sh(*args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = ws.main(argv)
    out = buf.getvalue().strip()
    return code, (json.loads(out) if out else None)


def dead_pid():
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


class RepoCase(unittest.TestCase):
    """A main checkout with a bare origin that has main and feature branches."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(os.path.realpath(self.tmp.name))
        self.origin = root / "origin.git"
        self.main = root / "repo with space"
        sh("git", "init", "-q", "--bare", "-b", "main", str(self.origin), cwd=root)
        sh("git", "init", "-q", "-b", "main", str(self.main), cwd=root)
        for k, v in (("user.email", "t@example.com"), ("user.name", "t")):
            sh("git", "config", k, v, cwd=self.main)
        (self.main / "a.txt").write_text("a\n")
        (self.main / "b.txt").write_text("b\n")
        sh("git", "add", ".", cwd=self.main)
        sh("git", "commit", "-q", "-m", "init", cwd=self.main)
        sh("git", "remote", "add", "origin", str(self.origin), cwd=self.main)
        sh("git", "push", "-q", "origin", "main", cwd=self.main)
        sh("git", "remote", "set-head", "origin", "main", cwd=self.main)
        sh("git", "push", "-q", "origin", "main:feature", cwd=self.main)
        (self.main / ".venv").mkdir()
        self.old_cwd = os.getcwd()
        os.chdir(self.main)

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.tmp.cleanup()


class PathsTests(RepoCase):
    def test_paths_from_main_and_from_worktree(self):
        code, out = run(["paths"])
        self.assertEqual(code, 0)
        self.assertEqual(out["main"], str(self.main))
        self.assertEqual(out["base"], "main")
        self.assertEqual(out["common_dir"], str(self.main / ".git"))
        _, wt = run(["worktree", "add", "pr-1", "feature"])
        _, out = run(["paths", "--worktree", wt["path"]])
        self.assertEqual(out["main"], str(self.main))
        self.assertEqual(out["common_dir"], str(self.main / ".git"))
        self.assertTrue(out["git_dir"].startswith(str(self.main / ".git" / "worktrees")))

    def test_statedir_common_and_worktree(self):
        _, out = run(["statedir", "backlog-sprint", "--common"])
        self.assertEqual(out["dir"], str(self.main / ".git" / "backlog-sprint"))
        self.assertTrue(Path(out["dir"]).is_dir())


class LockTests(RepoCase):
    def lock_path(self):
        return self.main / ".git" / "review-loop" / "lock"

    def test_acquire_then_held_by_live_other(self):
        code, out = run(["lock", "acquire", "review-loop", "--pid", "999999999"])
        # pid 999999999 is not alive, but it is ours for this call: taken.
        self.assertEqual(code, 0)
        self.assertTrue(out["acquired"])
        self.lock_path().write_text(json.dumps({"pid": os.getpid(), "started_at": "x"}))
        code, out = run(["lock", "acquire", "review-loop", "--pid", "999999999"])
        self.assertEqual(code, 3)
        self.assertEqual(out["holder"]["pid"], os.getpid())

    def test_stale_lock_is_replaced(self):
        self.lock_path().parent.mkdir(parents=True)
        self.lock_path().write_text(json.dumps({"pid": dead_pid(), "started_at": "x"}))
        code, out = run(["lock", "acquire", "review-loop", "--pid", "4242"])
        self.assertEqual(code, 0)
        self.assertIsNotNone(out["replaced"])
        held = json.loads(self.lock_path().read_text())
        self.assertEqual(held["pid"], 4242)
        self.assertRegex(held["started_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_own_lock_is_a_resume(self):
        run(["lock", "acquire", "review-loop", "--pid", str(os.getpid())])
        code, out = run(["lock", "acquire", "review-loop", "--pid", str(os.getpid())])
        self.assertEqual(code, 0)
        self.assertEqual(out["replaced"]["pid"], os.getpid())

    def test_release_only_own(self):
        run(["lock", "acquire", "review-loop", "--pid", str(os.getpid())])
        code, out = run(["lock", "release", "review-loop", "--pid", "4242"])
        self.assertEqual(code, 3)
        self.assertTrue(self.lock_path().exists())
        code, out = run(["lock", "release", "review-loop", "--pid", str(os.getpid())])
        self.assertEqual(code, 0)
        self.assertFalse(self.lock_path().exists())
        code, out = run(["lock", "release", "review-loop", "--pid", "1"])
        self.assertEqual((code, out["released"]), (0, False))

    def test_show(self):
        run(["lock", "acquire", "review-loop", "--pid", str(os.getpid())])
        _, out = run(["lock", "show", "review-loop", "--pid", str(os.getpid())])
        self.assertTrue(out["alive"])
        self.assertTrue(out["ours"])

    def test_worktree_lock_lives_in_its_git_dir(self):
        _, wt = run(["worktree", "add", "pr-2", "feature"])
        _, out = run(["lock", "acquire", "review-loop", "--worktree", wt["path"], "--pid", "7"])
        self.assertIn(os.sep + "worktrees" + os.sep + "pr-2", out["lock"])


class SessionPidTests(unittest.TestCase):
    def test_is_claude(self):
        self.assertTrue(ws.is_claude("/usr/local/bin/claude -p hi"))
        self.assertTrue(ws.is_claude("node /usr/lib/node_modules/@anthropic-ai/claude-code/cli.js"))
        self.assertFalse(ws.is_claude("/bin/zsh -c python3 x.py"))
        self.assertFalse(ws.is_claude("python3 claude_notes.py"))
        # The shell Claude Code spawns mentions claude paths in its arguments.
        self.assertFalse(ws.is_claude(
            "/bin/zsh -c source ~/.claude/shell-snapshots/s.sh && python3 claude-code/.claude/scripts/x.py"))

    def test_session_pid_is_a_live_ancestor(self):
        self.assertTrue(ws.pid_alive(ws.session_pid()))


class MetricsTests(RepoCase):
    def test_append_one_compact_line_per_call(self):
        run(["metrics-append", "review-loop-metrics.jsonl", '{"run": 1, "pr": 3}'])
        run(["metrics-append", "review-loop-metrics.jsonl", '{"run": 2, "pr": 3}'])
        lines = (self.main / ".git" / "review-loop-metrics.jsonl").read_text().splitlines()
        self.assertEqual([json.loads(x)["run"] for x in lines], [1, 2])

    def test_rejects_bad_json_and_paths_stay_in_git_dir(self):
        code, _ = run(["metrics-append", "m.jsonl", "{not json"])
        self.assertEqual(code, 2)
        run(["metrics-append", "../escape.jsonl", "{}"])
        self.assertTrue((self.main / ".git" / "escape.jsonl").exists())
        self.assertFalse((self.main / "escape.jsonl").exists())


class MetricsShowTests(RepoCase):
    def test_highest_run_for_the_pr(self):
        run(["metrics-append", "review-loop-metrics.jsonl", '{"type": "run", "run": 1, "pr": 3}'])
        run(["metrics-append", "review-loop-metrics.jsonl", '{"type": "run", "run": 2, "pr": 3}'])
        run(["metrics-append", "review-loop-metrics.jsonl", '{"type": "run", "run": 5, "pr": 4}'])
        _, out = run(["metrics-show", "--pr", "3"])
        self.assertEqual(out["record"]["run"], 2)
        _, out = run(["metrics-show", "--pr", "9"])
        self.assertIsNone(out["record"])

    def test_no_file(self):
        _, out = run(["metrics-show", "--pr", "1"])
        self.assertIsNone(out["record"])


class CheckTests(RepoCase):
    def write_config(self, root, cfg):
        (Path(root) / ".claude").mkdir(exist_ok=True)
        (Path(root) / ".claude" / "review-loop.json").write_text(json.dumps(cfg))

    def test_runs_in_the_worktree_and_fills_tests(self):
        _, wt = run(["worktree", "add", "pr-3", "feature"])
        self.write_config(self.main, {
            "lint_commands": ["pwd", "test -f a.txt"],
            "test_command": "echo ran {tests}"})
        code, out = run(["check", "lint", "--worktree", wt["path"]])
        self.assertEqual(code, 0)
        self.assertEqual(out["results"][0]["output"].strip(), wt["path"])
        code, out = run(["check", "test", "--worktree", wt["path"], "--tests", "tests/a b.py"])
        self.assertEqual(out["results"][0]["output"].strip(), "ran tests/a b.py")
        code, out = run(["check", "test", "--worktree", wt["path"]])
        self.assertEqual(out["results"][0]["command"], "echo ran")

    def test_worktree_config_wins_and_failure_exits_4(self):
        _, wt = run(["worktree", "add", "pr-4", "feature"])
        self.write_config(self.main, {"lint_commands": ["true"]})
        self.write_config(wt["path"], {"lint_commands": ["true", "false"]})
        code, out = run(["check", "lint", "--worktree", wt["path"]])
        self.assertEqual(code, 4)
        self.assertEqual([r["exit"] for r in out["results"]], [0, 1])

    def test_nothing_configured(self):
        code, out = run(["check", "test", "--worktree", str(self.main)])
        self.assertEqual(code, 2)
        self.assertIn("test_command", out["reason"])


class WorktreeTests(RepoCase):
    def test_add_find_remove_with_links(self):
        code, out = run(["worktree", "add", "pr-5", "feature", "--link", ".venv", "--link", ".env"])
        self.assertEqual(code, 0)
        wt = Path(out["path"])
        self.assertEqual(wt, self.main / ".claude" / "worktrees" / "pr-5")
        self.assertEqual(out["linked"], [".venv"])  # .env does not exist in main
        self.assertTrue((wt / ".venv").is_symlink())
        _, found = run(["worktree", "find", "feature"])
        self.assertEqual(found["path"], str(wt))
        code, out = run(["worktree", "remove", str(wt)])
        self.assertEqual(code, 0)
        self.assertEqual(out["unlinked"], [".venv"])
        self.assertFalse(wt.exists())
        self.assertTrue((self.main / ".venv").is_dir())
        _, found = run(["worktree", "find", "feature"])
        self.assertIsNone(found["path"])

    def test_new_branch_from_base(self):
        code, out = run(["worktree", "add", "8", "fix/8-x", "--start", "origin/main"])
        self.assertEqual(code, 0)
        self.assertEqual(out["start"], "origin/main")

    def test_remove_refuses_uncommitted_work(self):
        _, out = run(["worktree", "add", "pr-6", "feature"])
        Path(out["path"], "a.txt").write_text("changed\n")
        code, _ = run(["worktree", "remove", out["path"]])
        self.assertEqual(code, 1)
        self.assertTrue(Path(out["path"]).exists())

    def test_add_existing_path_fails(self):
        run(["worktree", "add", "pr-7", "feature"])
        code, _ = run(["worktree", "add", "pr-7", "feature"])
        self.assertEqual(code, 1)


class OverlapTests(RepoCase):
    def test_files_changed_on_both_sides(self):
        _, out = run(["worktree", "add", "pr-9", "feature"])
        wt = out["path"]
        for k, v in (("user.email", "t@example.com"), ("user.name", "t")):
            sh("git", "config", k, v, cwd=wt)
        Path(wt, "a.txt").write_text("feature\n")
        Path(wt, "c.txt").write_text("new\n")
        sh("git", "commit", "-qam", "f", cwd=wt)
        sh("git", "add", "c.txt", cwd=wt)
        sh("git", "commit", "-qm", "c", cwd=wt)
        (self.main / "a.txt").write_text("main\n")
        (self.main / "b.txt").write_text("main\n")
        sh("git", "commit", "-qam", "m", cwd=self.main)
        sh("git", "push", "-q", "origin", "main", cwd=self.main)
        code, out = run(["overlap", "main", "--worktree", wt])
        self.assertEqual(code, 0)
        self.assertEqual(out["files"], ["a.txt"])


if __name__ == "__main__":
    unittest.main()
