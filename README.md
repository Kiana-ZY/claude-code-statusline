# Claude Code Session Token Monitor

A multi-line statusline plugin for [Claude Code](https://claude.ai/code) that displays real-time session token usage, context window consumption, cost, and more.

## Display

```
[MiniMax-M2.7] ⑂ Python_Project | effort: high | ✊ think
█████░░░░░ 52% | In(unc): 500.4K | Out: 55.3K | Cache: +99.0K/14.5M | Total: 15.2M
¥ $0.12 | ⏱️ 12m30s | +156 -23 | 5h:24% | 7d:41%
```

### Line 1 — Session Info
- Model name, working directory, git branch & staged/modified files
- Effort level (`low`/`medium`/`high`/`max`)
- Thinking (extended thinking) status

### Line 2 — Token Usage
- **Progress bar** — context window usage with color-coded bar (green < 80%, yellow 80-95%, red ≥ 95%)
- **In(uncached)** — uncached input tokens
- **Out** — output tokens
- **Cache** — creation (+) / read (/) tokens
- **Total** — all tokens combined

### Line 3 — Cost & Limits
- Estimated session cost in USD
- Session duration
- Code lines added/removed
- Rate limit usage (5h and 7d, for Pro/Max subscribers)

## Features

- Multi-line display for rich context
- Progress bar visualization for context window
- Session token tracking from JSONL transcript with incremental caching
- Context usage derived from JSONL (works with non-Anthropic providers like MiniMax, DeepSeek)
- Git branch and change indicators
- Cost and duration tracking
- Effort level and thinking status
- Rate limit monitoring
- ANSI color output
- UTF-8 compatible on Windows

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

Replace `python3` with your Python executable path if needed (e.g., `D:/work/miniconda/python` on Windows).

3. Restart Claude Code or send a new message — the statusline updates automatically.

## How It Works

- Reads JSON session data from Claude Code via stdin (model, cost, effort, rate limits, etc.)
- Parses the session JSONL transcript to compute cumulative token totals
- Uses file-size-based caching for efficient incremental updates
- Deduplicates API calls by `message.id` to avoid double-counting
- Derives context usage from JSONL for non-Anthropic model compatibility

## Testing

```bash
echo '{"session_id":"test","transcript_path":"path/to/session.jsonl","model":{"display_name":"MiniMax-M2.7"},"workspace":{"current_dir":"D:/work/Python_Project"},"context_window":{"context_window_size":1000000},"cost":{"total_cost_usd":0.05,"total_duration_ms":120000},"effort":{"level":"high"},"thinking":{"enabled":true}}' | python3 ~/.claude/statusline/token_monitor.py
```

## License

MIT
