#!/usr/bin/env python3
"""Claude Code statusline hook: session token + context usage monitor."""
import json
import os
import sys

CACHE_PATH = os.path.expanduser("~/.claude/statusline/token_cache.json")

# ── ANSI ──────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"


# ── Helpers ───────────────────────────────────────
def fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def fmt_pct(val) -> str:
    if val is None:
        return "?"
    return f"{val:.0f}%"


def load_cache() -> dict:
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    tmp = CACHE_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, separators=(",", ":"))
        os.replace(tmp, CACHE_PATH)
    except Exception:
        pass


# ── JSONL parsing ─────────────────────────────────
def parse_jsonl(path: str, start_line: int, seen_ids: set) -> tuple:
    """Parse JSONL from start_line (1-based) to end.
    Returns (totals_dict, seen_ids, line_count, last_ctx_used)."""
    totals = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0}
    last_ctx_used = None
    if not os.path.isfile(path):
        return totals, seen_ids, 0, last_ctx_used

    lc = start_line - 1
    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if i < start_line:
                    continue
                lc = i
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("type") != "assistant":
                    continue
                msg = d.get("message", {})
                if not msg or "usage" not in msg:
                    continue
                mid = msg.get("id")
                if mid and mid in seen_ids:
                    continue

                usage = msg["usage"]
                totals["input"] += usage.get("input_tokens", 0)
                totals["output"] += usage.get("output_tokens", 0)
                totals["cache_create"] += usage.get("cache_creation_input_tokens", 0)
                totals["cache_read"] += usage.get("cache_read_input_tokens", 0)
                if mid:
                    seen_ids.add(mid)
                # Track last call's context usage (what was actually sent to model)
                last_ctx_used = (
                    usage.get("input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                )
    except Exception:
        pass
    return totals, seen_ids, lc, last_ctx_used


# ── Session totals (with caching) ─────────────────
def get_session_totals(transcript_path: str, cache: dict) -> tuple:
    """Returns (totals_dict, last_ctx_used)."""
    entry = cache.get(transcript_path, {})
    cached_totals = entry.get("totals", {})
    seen_ids = set(entry.get("seen_message_ids", []))
    prev_line_count = entry.get("line_count", 0)
    last_ctx_used = entry.get("last_ctx_used")

    try:
        file_size = os.path.getsize(transcript_path)
    except OSError:
        file_size = 0

    # Cache hit
    if entry and entry.get("file_size") == file_size and cached_totals:
        return cached_totals, last_ctx_used

    start_line = prev_line_count + 1 if prev_line_count > 0 else 1
    new_totals, seen_ids, line_count, new_ctx = parse_jsonl(transcript_path, start_line, seen_ids)

    totals = {
        "input": cached_totals.get("input", 0) + new_totals["input"],
        "output": cached_totals.get("output", 0) + new_totals["output"],
        "cache_create": cached_totals.get("cache_create", 0) + new_totals["cache_create"],
        "cache_read": cached_totals.get("cache_read", 0) + new_totals["cache_read"],
    }

    if new_ctx is not None:
        last_ctx_used = new_ctx

    cache[transcript_path] = {
        "line_count": line_count,
        "file_size": file_size,
        "seen_message_ids": list(seen_ids),
        "totals": totals,
        "last_ctx_used": last_ctx_used,
    }
    save_cache(cache)
    return totals, last_ctx_used


# ── Output formatting ─────────────────────────────
def format_statusline(model: str, totals: dict, ctx_used, ctx_size, ctx_pct) -> str:
    if ctx_used is not None and ctx_size is not None:
        ctx_val = f"{fmt_num(ctx_used)} / {fmt_num(ctx_size)}"
    else:
        ctx_val = "?"

    pct_str = fmt_pct(ctx_pct)
    if isinstance(ctx_pct, (int, float)):
        if ctx_pct >= 95:
            color = RED
        elif ctx_pct >= 80:
            color = YELLOW
        else:
            color = GREEN
        ctx_str = f"{ctx_val} ({color}{pct_str}{RESET})"
    else:
        ctx_str = f"{ctx_val} ({pct_str})"

    return (
        f"{BOLD}{CYAN}[{model}]{RESET}"
        f" | {BOLD}In(uncached):{RESET} {fmt_num(totals['input'])}"
        f" | {BOLD}Out:{RESET} {fmt_num(totals['output'])}"
        f" | {BOLD}Cache:{RESET} +{fmt_num(totals['cache_create'])}"
        f" / {fmt_num(totals['cache_read'])}"
        f" | {BOLD}Total:{RESET} {fmt_num(totals['input'] + totals['output'] + totals['cache_create'] + totals['cache_read'])}"
        f" | {BOLD}Ctx:{RESET} {ctx_str}"
    )


# ── Main ──────────────────────────────────────────
def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        return

    model = (data.get("model") or {}).get("display_name", data.get("model", {}).get("id", "?"))
    ctx = data.get("context_window") or {}
    ctx_size = ctx.get("context_window_size")

    transcript_path = data.get("transcript_path", "")
    if transcript_path and os.path.isfile(transcript_path):
        cache = load_cache()
        totals, jsonl_ctx = get_session_totals(transcript_path, cache)
    else:
        totals = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0}
        jsonl_ctx = None

    # Prefer JSONL-derived context usage — Claude Code's total_input_tokens
    # doesn't update reliably for non-Anthropic models (MiniMax, DeepSeek, etc.)
    if jsonl_ctx is not None:
        ctx_used = jsonl_ctx
    else:
        ctx_used = ctx.get("total_input_tokens")

    if ctx_used is not None and ctx_size is not None and ctx_size > 0:
        ctx_pct = ctx_used / ctx_size * 100
    else:
        ctx_pct = ctx.get("used_percentage")

    print(format_statusline(model, totals, ctx_used, ctx_size, ctx_pct))


if __name__ == "__main__":
    main()
