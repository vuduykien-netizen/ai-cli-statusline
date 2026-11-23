#!/usr/bin/env python3
"""Install the status line for Claude Code and/or the Codex CLI.

    python install.py              # both
    python install.py --claude     # Claude Code only
    python install.py --codex      # Codex CLI only
    python install.py --dry-run    # show what would change, write nothing
    python install.py --force      # replace a status line you already have

Claude Code: copies claude/statusline.py to <config dir>/statusline-ai-cli.py and
sets "statusLine" in <config dir>/settings.json. Config dir = $CLAUDE_CONFIG_DIR
or ~/.claude.
Codex CLI: sets [tui] status_line in <codex home>/config.toml. Codex home =
$CODEX_HOME or ~/.codex.

Every file it changes is backed up first as <file>.bak-<timestamp>. An existing
status line is left alone unless you pass --force.
"""
import argparse
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CODEX_ITEMS = ["project-name", "git-branch", "model-with-reasoning", "context-used", "five-hour-limit", "weekly-limit"]
STAMP = time.strftime("%Y%m%d-%H%M%S")


def backup(path, dry):
    if os.path.exists(path):
        dst = "%s.bak-%s" % (path, STAMP)
        print("  backup  %s" % dst)
        if not dry:
            shutil.copy2(path, dst)


def install_claude(force, dry):
    cfg = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    settings = os.path.join(cfg, "settings.json")
    target = os.path.join(cfg, "statusline-ai-cli.py")
    print("Claude Code (%s)" % cfg)
    data = {}
    if os.path.exists(settings):
        with open(settings, encoding="utf-8") as f:
            data = json.load(f)
    old = data.get("statusLine")
    if old and "statusline-ai-cli.py" not in json.dumps(old) and not force:
        print("  skip    settings.json already has a statusLine (use --force to replace):")
        print("          %s" % json.dumps(old, ensure_ascii=False))
        return False
    py = sys.executable.replace("\\", "/")
    data["statusLine"] = {"type": "command", "command": '"%s" "%s"' % (py, target.replace("\\", "/")), "padding": 0}
    print("  copy    %s" % target)
    print("  set     statusLine = %s" % data["statusLine"]["command"])
    if not dry:
        os.makedirs(cfg, exist_ok=True)
        shutil.copy2(os.path.join(HERE, "claude", "statusline.py"), target)
        backup(settings, dry)
        tmp = settings + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, settings)
    else:
        backup(settings, dry)
    return True


def set_tui_status_line(text, items, force):
    """Return (new_text, message). Edits only the status_line key inside [tui]."""
    value = "status_line = [%s]" % ", ".join('"%s"' % i for i in items)
    lines = text.splitlines()
    header = re.compile(r"^\s*\[\s*tui\s*\]\s*(#.*)?$")
    any_table = re.compile(r"^\s*\[")
    start = next((i for i, l in enumerate(lines) if header.match(l)), None)
    if start is None:
        sep = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
        return text + sep + "[tui]\n" + value + "\n", "added [tui] table"
    end = next((i for i in range(start + 1, len(lines)) if any_table.match(lines[i])), len(lines))
    key = re.compile(r"^\s*status_line\s*=")
    for i in range(start + 1, end):
        if key.match(lines[i]):
            j = i
            depth = lines[i].count("[") - lines[i].count("]")
            while depth > 0 and j + 1 < end:  # multi-line array
                j += 1
                depth += lines[j].count("[") - lines[j].count("]")
            current = " ".join(x.strip() for x in lines[i:j + 1])
            if current.replace(" ", "") == value.replace(" ", ""):
                return text, "already set"
            if not force:
                return None, "status_line already set to %s (use --force to replace)" % current
            new = lines[:i] + [value] + lines[j + 1:]
            return "\n".join(new) + "\n", "replaced status_line"
    new = lines[:start + 1] + [value] + lines[start + 1:]
    return "\n".join(new) + "\n", "added status_line to [tui]"


def install_codex(force, dry):
    home = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    cfg = os.path.join(home, "config.toml")
    print("Codex CLI (%s)" % home)
    text = ""
    if os.path.exists(cfg):
        with open(cfg, encoding="utf-8") as f:
            text = f.read()
    new, msg = set_tui_status_line(text, CODEX_ITEMS, force)
    if new is None:
        print("  skip    " + msg)
        return False
    print("  %s" % msg)
    if new == text:
        return True
    backup(cfg, dry)
    if not dry:
        os.makedirs(home, exist_ok=True)
        tmp = cfg + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
        os.replace(tmp, cfg)
    return True


def main():
    ap = argparse.ArgumentParser(description="Install the status line for Claude Code and Codex CLI.")
    ap.add_argument("--claude", action="store_true", help="Claude Code only")
    ap.add_argument("--codex", action="store_true", help="Codex CLI only")
    ap.add_argument("--force", action="store_true", help="replace an existing status line")
    ap.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    a = ap.parse_args()
    both = not a.claude and not a.codex
    ok = True
    if a.claude or both:
        ok = install_claude(a.force, a.dry_run) and ok
    if a.codex or both:
        ok = install_codex(a.force, a.dry_run) and ok
    print("Done." if ok else "Done, with skipped steps (see above).")
    print("Restart Claude Code / Codex to see the new line.")


if __name__ == "__main__":
    main()
