# ai-cli-statusline

One status line for **Claude Code** and the **OpenAI Codex CLI**. It shows the same facts under the prompt of both tools:

```
my-project │ main │ Opus 5.5 · high │ ctx 23% │ 5h 41% ↻1h20m │ 7d 62% ↻3d4h
```

| Item | Meaning |
|---|---|
| `my-project` | project folder |
| `main` | git branch (hidden outside a git repo) |
| `Opus 5.5 · high` | model and reasoning effort |
| `ctx 23%` | context window used |
| `5h 41% ↻1h20m` | 5-hour usage limit used, time until it resets |
| `7d 62% ↻3d4h` | weekly usage limit used, time until it resets |

Percentages turn yellow from 50% and red from 80%. Items with no data are left out.

## Install

Needs Python 3.8 or newer. No packages to install.

```bash
git clone https://github.com/vuduykien-netizen/ai-cli-statusline.git
cd ai-cli-statusline
python install.py --dry-run   # see what will change
python install.py             # Claude Code + Codex
```

Use `--claude` or `--codex` to install only one. The installer backs up every file it changes (`<file>.bak-<timestamp>`). If you already have a status line, it leaves it alone unless you add `--force`. Restart the tool after installing.

### Claude Code by hand

Copy `claude/statusline.py` somewhere and add this to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /path/to/statusline.py"
  }
}
```

On Windows use the full path of `python.exe`, with forward slashes.

Options (environment variables):
- `NO_COLOR=1`: plain text, no colors
- `STATUSLINE_ASCII=1`: ASCII only, for terminals that cannot show `│` and `↻`

### Codex CLI by hand

Add the `status_line` key to the `[tui]` table of `~/.codex/config.toml` (see [`codex/config.toml`](codex/config.toml)):

```toml
[tui]
status_line = ["project-name", "git-branch", "model-with-reasoning", "context-used", "five-hour-limit", "weekly-limit"]
```

Codex draws this line itself from its built-in items, so there is no script to run. Inside Codex, `/statusline` changes the items for the current session. Tested with codex-cli 0.169.

## How it works

- **Claude Code** pipes a JSON snapshot of the session (model, workspace, context window, `rate_limits`) to the script on stdin and prints the first line the script writes. The script reads the git branch from `.git/HEAD` without starting git, so it stays fast.
- **Codex** has a built-in status line made of named items. The config picks the items that match the Claude line.

## Privacy and safety

The Claude script only reads the JSON on stdin and `.git/HEAD`. It does not call the network, does not write files, and never reads your conversation. It never exits with an error, so a bad input cannot break your terminal.

## Tests

```bash
python -m unittest discover -s tests
```

## Tiếng Việt

Thanh trạng thái chung cho Claude Code và Codex CLI: tên thư mục dự án, nhánh git, mô hình và mức suy nghĩ, phần ngữ cảnh đã dùng, hạn mức 5 giờ và hạn mức tuần (kèm thời gian còn lại tới lúc đặt lại). Cài: `python install.py` (xem trước bằng `--dry-run`). Bộ cài sao lưu mọi tệp trước khi sửa và không đè thanh trạng thái đang có nếu không thêm `--force`.

## License

MIT
