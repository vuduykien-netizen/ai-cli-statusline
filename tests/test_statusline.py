import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["NO_COLOR"] = "1"


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sl = load("statusline", "claude/statusline.py")
inst = load("install", "install.py")

NOW = 1_800_000_000
SAMPLE = {
    "model": {"id": "claude-opus-5-5", "display_name": "Claude Opus 5.5"},
    "effort": {"level": "high"},
    "workspace": {"current_dir": "/nonexistent/my-project", "project_dir": "/nonexistent/my-project"},
    "context_window": {"used_percentage": 23.4},
    "rate_limits": {
        "five_hour": {"used_percentage": 41, "resets_at": NOW + 80 * 60},
        "seven_day": {"used_percentage": 82.6, "resets_at": NOW + 3 * 86400 + 4 * 3600},
    },
}


class StatusLine(unittest.TestCase):
    def test_full_line(self):
        self.assertEqual(sl.build(SAMPLE, now=NOW),
                         "my-project │ Opus 5.5 · high │ ctx 23% │ 5h 41% ↻1h20m │ 7d 83% ↻3d4h")

    def test_empty_and_garbage(self):
        self.assertEqual(sl.build({}, now=NOW), "")
        self.assertEqual(sl.build(None, now=NOW), "")
        self.assertEqual(sl.build({"rate_limits": "x", "model": 5, "context_window": []}, now=NOW), "")

    def test_iso_reset_and_past_reset(self):
        d = {"rate_limits": {"five_hour": {"used_percentage": 10, "resets_at": "2027-01-15T08:00:00Z"},
                             "seven_day": {"used_percentage": 5, "resets_at": "2027-01-15T06:00:00Z"}}}
        out = sl.build(d, now=sl.to_epoch("2027-01-15T06:30:00Z"))
        self.assertEqual(out, "5h 10% ↻1h30m │ 7d 5%")

    def test_context_from_tokens(self):
        d = {"context_window": {"context_window_size": 200000,
                                "current_usage": {"input_tokens": 30000, "cache_read_input_tokens": 20000,
                                                  "output_tokens": 999999}}}
        self.assertEqual(sl.build(d, now=NOW), "ctx 25%")

    def test_git_branch_and_worktree_file(self):
        with tempfile.TemporaryDirectory() as t:
            os.makedirs(os.path.join(t, "repo", ".git"))
            with open(os.path.join(t, "repo", ".git", "HEAD"), "w") as f:
                f.write("ref: refs/heads/feature/x\n")
            sub = os.path.join(t, "repo", "src", "deep")
            os.makedirs(sub)
            self.assertEqual(sl.git_branch({"cwd": sub}), "feature/x")
            wt = os.path.join(t, "wt")
            os.makedirs(os.path.join(t, "gitdir"))
            os.makedirs(wt)
            with open(os.path.join(t, "gitdir", "HEAD"), "w") as f:
                f.write("0123456789abcdef\n")
            with open(os.path.join(wt, ".git"), "w") as f:
                f.write("gitdir: " + os.path.join(t, "gitdir") + "\n")
            self.assertEqual(sl.git_branch({"cwd": wt}), "0123456")

    def test_script_never_fails(self):
        for stdin in (b"", b"not json", json.dumps(SAMPLE).encode()):
            r = subprocess.run([sys.executable, os.path.join(ROOT, "claude", "statusline.py")],
                               input=stdin, capture_output=True, timeout=10)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout.count(b"\n"), 1)


class CodexConfig(unittest.TestCase):
    items = ["a", "b"]

    def test_add_table(self):
        new, msg = inst.set_tui_status_line('model = "x"\n', self.items, False)
        self.assertEqual(new, 'model = "x"\n\n[tui]\nstatus_line = ["a", "b"]\n')

    def test_add_key_in_existing_table(self):
        src = "[tui]\nfoo = true\n\n[other]\nx = 1\n"
        new, _ = inst.set_tui_status_line(src, self.items, False)
        self.assertEqual(new, '[tui]\nstatus_line = ["a", "b"]\nfoo = true\n\n[other]\nx = 1\n')

    def test_keep_existing_without_force(self):
        src = '[tui]\nstatus_line = ["z"]\n'
        new, msg = inst.set_tui_status_line(src, self.items, False)
        self.assertIsNone(new)
        new, _ = inst.set_tui_status_line(src, self.items, True)
        self.assertEqual(new, '[tui]\nstatus_line = ["a", "b"]\n')

    def test_replace_multiline_array(self):
        src = '[tui]\nstatus_line = [\n  "z",\n  "y",\n]\nfoo = 1\n[tui.sub]\nk = 2\n'
        new, _ = inst.set_tui_status_line(src, self.items, True)
        self.assertEqual(new, '[tui]\nstatus_line = ["a", "b"]\nfoo = 1\n[tui.sub]\nk = 2\n')

    def test_ignores_subtable_header(self):
        src = "[tui.model_availability_nux]\nx = 4\n"
        new, msg = inst.set_tui_status_line(src, self.items, False)
        self.assertTrue(new.endswith('[tui]\nstatus_line = ["a", "b"]\n'))


if __name__ == "__main__":
    unittest.main()
