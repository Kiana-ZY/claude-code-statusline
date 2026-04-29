# Claude Code Session Token Monitor

A lightweight statusline plugin for [Claude Code](https://claude.ai/code) that displays real-time session token usage and context window consumption in the terminal.

## Features

- **Model display** — Shows the current model name
- **Session totals** — Cumulative input / output / cache tokens for the current session
- **Cache breakdown** — Cache creation (`+`) and cache read (`/`) tokens
- **Context window** — Current context usage with token count and percentage

## Display

```
[MiniMax M2.7] | In: 230.5K | Out: 26.2K | Cache: +99.0K / 5.1M | Total: 5.5M | Ctx: 15.2K / 200.0K (8%)
```

Context indicator colors:
- Green (< 80%)
- Yellow (80% ~ 95%)
- Red (≥ 95%)

## Requirements

- Python 3.7+
- No external dependencies

## Installation

1. Copy `token_monitor.py` to `~/.claude/statusline/token_monitor.py`

2. Add the `statusLine` block to your `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/statusline/token_monitor.py"
  }
}
```

Replace `python3` with your Python executable path if needed.

3. Restart Claude Code or send a new message — the statusline updates automatically.

## How It Works

- Reads session data from Claude Code's statusline hook stdin
- Parses the session JSONL transcript to compute cumulative token totals
- Uses file-size-based caching for efficient incremental updates
- Deduplicates API calls by `message.id` to avoid double-counting

## License

MIT
