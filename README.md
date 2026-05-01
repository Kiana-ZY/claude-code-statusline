# Claude Code Statusline — Dracula Theme + Token Tracking

A Dracula-themed statusline for [Claude Code](https://claude.ai/code) with real-time session token tracking, context window monitoring, and cost display.

## Display

```
◈ mimo-v2.5-pro | [■■■■■■■■■■■□□□□□□□□□] 118.2K/200.0K (59%) | In:606.3K Out:90.3K Cache:+99.0K/22.4M Total:23.2M | $4.70 | ⏱ 1h4m | +309 -128 | ↯ max | ⌂ Python_Project
```

### Columns

| Column | Icon | Description |
|--------|------|-------------|
| Model | `◈` | Active model name |
| Context | `[■■■□□□]` | Progress bar with used/total (pct%), traffic-light colors |
| Tokens | `In:` `Out:` `Cache:` `Total:` | Session token stats from JSONL |
| Cost | `$` | Session API spend (hidden when < $0.01) |
| Duration | `⏱` | Session duration |
| Changes | `+N -N` | Code lines added/removed |
| Effort | `↯` | Effort level, colored by intensity |
| Style | `❋` | Output style (hidden when "default") |
| Dir | `⌂` | Repo directory basename |
| Worktree | `⊕` | Worktree label (hidden outside worktrees) |
| Git | `⎇` | Git branch, yellow when dirty |

### Traffic-light colors

| Context remaining | Effort level | Color |
|-------------------|--------------|-------|
| > 50% | `low` | Green |
| 20-50% | `medium` | Yellow |
| < 20% | `high`/`max` | Red (bold for effort) |

## Architecture

```
~/.claude/scripts/
  statusline.sh       # Bash script — Dracula theme, ANSI colors, jq parsing
  token_helper.py     # Python helper — JSONL incremental parsing with cache
  token_cache.json    # Runtime cache (auto-created)
```

- **statusline.sh** — Receives JSON from Claude Code via stdin, calls token_helper.py for token stats, outputs Dracula-themed ANSI text
- **token_helper.py** — Parses JSONL transcript to compute cumulative token totals (In/Out/Cache/Total) with file-size-based incremental caching

## Requirements

- `jq` — JSON parsing in bash
- Python 3.7+ — Token tracking (no external deps)
- Git Bash / WSL / Linux / macOS

## Installation

### Option 1: Manual

1. Copy `statusline.sh` and `token_helper.py` to `~/.claude/scripts/`

2. Add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/scripts/statusline.sh",
    "refreshInterval": 2
  }
}
```

3. On Windows, ensure Python is in PATH or edit the `PYTHON` detection in `statusline.sh`

### Option 2: webup-statusline skill

```bash
npx skills add webup/skills-cc -s webup-statusline -g
```

Then run `/webup-statusline` in Claude Code, and add token tracking manually.

## How It Works

1. Claude Code passes session JSON to stdin (model, context window, cost, etc.)
2. `statusline.sh` extracts fields with `jq`, calls `token_helper.py` for token stats
3. `token_helper.py` incrementally parses the JSONL transcript, caching results by file size
4. Context usage uses `current_usage` from stdin JSON (matches `/context` command)
5. Token totals (In/Out/Cache/Total) are derived from JSONL with `message.id` deduplication
6. `refreshInterval: 2` re-runs the script every 2 seconds for terminal resize adaptation

## Testing

```bash
echo '{"session_id":"test","transcript_path":"/path/to/session.jsonl","model":{"display_name":"mimo-v2.5-pro"},"workspace":{"current_dir":"/your/project"},"context_window":{"context_window_size":200000,"current_usage":{"input_tokens":3200,"cache_read_input_tokens":115000,"cache_creation_input_tokens":0}},"cost":{"total_cost_usd":4.70,"total_duration_ms":3846967}}' | bash ~/.claude/scripts/statusline.sh
```

## License

MIT
