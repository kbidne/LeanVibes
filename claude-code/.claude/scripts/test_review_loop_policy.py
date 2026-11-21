"""Tests for review_loop_policy.py. Run: python3 -m unittest discover -s claude-code/.claude/scripts"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import review_loop_policy as pol  # noqa: E402

CONFIG = {
    "risky_paths": ["src/payments/", "*.sql"],
    "always_ask_paths": ["migrations/"],
}


class MatchTests(unittest.TestCase):
    def test_directory_prefix(self):
        self.assertTrue(pol.matches("src/payments/charge.py", "src/payments/"))
        self.assertFalse(pol.matches("src/payments_old/charge.py", "src/payments/"))

    def test_glob_matches_basename(self):
        self.assertTrue(pol.matches("db/schema.sql", "*.sql"))
        self.assertFalse(pol.matches("db/schema.sql.bak", "*.sql"))

    def test_leading_dot_slash_is_ignored_but_dotdirs_survive(self):
        self.assertTrue(pol.matches("./.github/workflows/ci.yml", ".github/workflows/"))
        self.assertTrue(pol.matches("./src/payments/x.py", "src/payments/"))


class EvaluateTests(unittest.TestCase):
    def test_ordinary_pr(self):
        r = pol.evaluate(["README.md", "src/ui/button.tsx"], CONFIG)
        self.assertFalse(r["risky"])
        self.assertTrue(r["auto_accept"])

    def test_risky_but_auto_accept(self):
        r = pol.evaluate(["src/payments/charge.py"], CONFIG)
        self.assertTrue(r["risky"])
        self.assertEqual(r["risky_files"], ["src/payments/charge.py"])
        self.assertTrue(r["auto_accept"])

    def test_always_ask(self):
        r = pol.evaluate(["migrations/0002.py", "README.md"], CONFIG)
        self.assertFalse(r["auto_accept"])
        self.assertEqual(r["always_ask_files"], ["migrations/0002.py"])
        self.assertIn("migrations/", r["reasons"][0])

    def test_workflows_always_ask_even_without_config(self):
        r = pol.evaluate([".github/workflows/ci.yml"], {})
        self.assertFalse(r["auto_accept"])

    def test_bad_pattern_list_raises(self):
        with self.assertRaises(ValueError):
            pol.evaluate(["a"], {"risky_paths": "src/"})


class MainTests(unittest.TestCase):
    def run_main(self, files, config=None):
        with tempfile.TemporaryDirectory() as d:
            files_path = Path(d, "files.txt")
            files_path.write_text("\n".join(files) + "\n")
            argv = ["--files", str(files_path)]
            if config is not None:
                cfg = Path(d, "cfg.json")
                cfg.write_text(config if isinstance(config, str) else json.dumps(config))
                argv += ["--config", str(cfg)]
            out = io.StringIO()
            with redirect_stdout(out):
                rc = pol.main(argv)
            return rc, json.loads(out.getvalue())

    def test_exit_codes(self):
        self.assertEqual(self.run_main(["README.md"], CONFIG)[0], 0)
        rc, result = self.run_main(["migrations/1.py"], CONFIG)
        self.assertEqual(rc, 1)
        self.assertFalse(result["auto_accept"])

    def test_malformed_config_is_exit_2(self):
        rc, result = self.run_main(["README.md"], "{not json")
        self.assertEqual(rc, 2)
        self.assertIn("error", result)

    def test_missing_explicit_config_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            files_path = Path(d, "files.txt")
            files_path.write_text("README.md\n")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = pol.main(["--files", str(files_path), "--config", str(Path(d, "missing.json"))])
        self.assertEqual(rc, 2)

    def test_missing_args_is_exit_2(self):
        self.assertEqual(pol.main([]), 2)


if __name__ == "__main__":
    unittest.main()
