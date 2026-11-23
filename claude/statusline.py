#!/usr/bin/env python3
"""Status line for Claude Code.

Claude Code pipes a JSON snapshot of the session to this script on stdin and
shows whatever the script prints as the line under the prompt. This script
prints one line such as:

    my-project │ main │ Opus 5.5 · high │ ctx 23% │ 5h 41% ↻1h20m │ 7d 62% ↻3d4h

Design rules:
- Standard library only, Python 3.8+.
- Never raises: a broken status line must not break the terminal.
- Read-only: no network calls, no files written, conversation content never read.
- Missing fields are skipped instead of shown as errors.

Environment variables:
- NO_COLOR=1            plain text, no ANSI colors
- STATUSLINE_ASCII=1    ASCII separators ("|" and "reset") for terminals without Unicode
"""
import json
import math
import os
import re
import sys
import time
from datetime import datetime

ASCII = bool(os.environ.get("STATUSLINE_ASCII"))
COLOR = not os.environ.get("NO_COLOR")
SEP = " | " if ASCII else " │ "
DOT = " - " if ASCII else " · "
RESET_MARK = " reset " if ASCII else " ↻"


def paint(text, code):
    return "\033[%sm%s\033[0m" % (code, text) if COLOR and text else text


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def pct_color(p):
    """Green under 50%, yellow under 80%, red from 80%."""
    if p >= 80:
        return "31"
    if p >= 50:
        return "33"
    return "32"


def project_name(data):
    ws = data.get("workspace") if isinstance(data.get("workspace"), dict) else {}
    for cand in (ws.get("project_dir"), ws.get("current_dir"), data.get("cwd")):
        if isinstance(cand, str) and cand.strip():
            parts = [x for x in re.split(r"[\\/]+", cand.strip()) if x]
            if parts and not re.fullmatch(r"[A-Za-z]:", parts[-1]):
                name = parts[-1]
                return name if len(name) <= 28 else name[:27] + "…"
    return ""


def git_branch(data):
    """Read .git/HEAD directly (no subprocess, so it stays fast)."""
    ws = data.get("workspace") if isinstance(data.get("workspace"), dict) else {}
    start = ws.get("current_dir") or data.get("cwd") or ""
    if not isinstance(start, str) or not start:
        return ""
    d = os.path.abspath(start)
    for _ in range(40):
        g = os.path.join(d, ".git")
        head = None
        if os.path.isdir(g):
            head = os.path.join(g, "HEAD")
        elif os.path.isfile(g):  # worktree or submodule: ".git" file points to the real git dir
            try:
                with open(g, encoding="utf-8", errors="replace") as f:
                    line = f.read().strip()
                if line.startswith("gitdir:"):
                    gd = line[7:].strip()
                    if not os.path.isabs(gd):
                        gd = os.path.join(d, gd)
                    head = os.path.join(gd, "HEAD")
            except OSError:
                return ""
        if head:
            try:
                with open(head, encoding="utf-8", errors="replace") as f:
                    ref = f.read().strip()
            except OSError:
                return ""
            if ref.startswith("ref: refs/heads/"):
                return ref[len("ref: refs/heads/"):]
            return ref[:7]
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return ""


def model_effort(data):
    m = data.get("model")
    name = ""
    if isinstance(m, dict):
        name = str(m.get("display_name") or m.get("id") or "")
    elif isinstance(m, str):
        name = m
    name = name.replace("Claude ", "").strip()[:24]
    ef = data.get("effort")
    if isinstance(ef, dict):
        ef = ef.get("level") or ef.get("value")
    ef = str(ef).strip()[:10] if ef else ""
    return DOT.join(x for x in (name, ef) if x)


def context_pct(data):
    cw = data.get("context_window")
    if not isinstance(cw, dict):
        return None
    if is_num(cw.get("used_percentage")):
        return float(cw["used_percentage"])
    if is_num(cw.get("remaining_percentage")):
        return 100.0 - float(cw["remaining_percentage"])
    size = cw.get("context_window_size")
    usage = cw.get("current_usage")
    if is_num(size) and size > 0 and isinstance(usage, dict):
        used = sum(v for k, v in usage.items() if is_num(v) and "token" in k and "output" not in k)
        if used:
            return 100.0 * used / size
    return None


def to_epoch(v):
    if is_num(v):
        return float(v) / 1000.0 if v > 1e11 else float(v)  # accept seconds or milliseconds
    if isinstance(v, str) and v:
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def countdown(epoch, now):
    s = int(epoch - now)
    if s <= 0:
        return ""
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m = s // 60
    if d:
        return "%dd%dh" % (d, h)
    if h:
        return "%dh%02dm" % (h, m)
    return "%dm" % m


def limit_part(rl, key, label, now):
    w = rl.get(key) if isinstance(rl, dict) else None
    if not isinstance(w, dict) or not is_num(w.get("used_percentage")):
        return ""
    p = float(w["used_percentage"])
    out = "%s %s" % (label, paint("%d%%" % round(p), pct_color(p)))
    ep = to_epoch(w.get("resets_at"))
    left = countdown(ep, now) if ep else ""
    if left:
        out += paint(RESET_MARK + left, "2")
    return out


def build(data, now=None):
    now = time.time() if now is None else now
    if not isinstance(data, dict):
        return ""
    parts = []
    proj = project_name(data)
    if proj:
        parts.append(paint(proj, "1"))
    br = git_branch(data)
    if br:
        parts.append(paint(br, "36"))
    me = model_effort(data)
    if me:
        parts.append(me)
    cp = context_pct(data)
    if cp is not None:
        parts.append("ctx " + paint("%d%%" % round(cp), pct_color(cp)))
    rl = data.get("rate_limits")
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        p = limit_part(rl, key, label, now)
        if p:
            parts.append(p)
    return paint(SEP, "2").join(parts) if COLOR else SEP.join(parts)


def main():
    try:
        raw = sys.stdin.buffer.read()
        data = json.loads(raw.decode("utf-8", errors="replace")) if raw.strip() else {}
    except Exception:
        data = {}
    try:
        line = build(data)
    except Exception:
        line = ""
    try:
        sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))
        sys.stdout.flush()
    except Exception:
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
