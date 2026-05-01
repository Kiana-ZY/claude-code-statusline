#!/usr/bin/env python3
"""Claude Code statusline hook: session token + context usage monitor.
Enhanced with official docs fields: cost, duration, effort, git, progress bar."""
import io
import json
import os
import subprocess
import sys
import time

# Force UTF-8 output for Windows GBK compatibility
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CACHE_PATH = os.path.expanduser("~/.claude/statusline/token_cache.json")

# ── ANSI ──────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"


# ── Helpers ───────────────────────────────────────
def fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def fmt_duration(ms: int) -> str:
    if ms <= 0:
        return "0s"
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h{m}m"
    if m > 0:
        return f"{m}m{s}s"
    return f"{s}s"


def fmt_pct(val) -> str:
    if val is None:
        return "?"
    return f"{val:.0f}%"


def progress_bar(pct: int, width: int = 10) -> str:
    if pct >= 95:
        color = RED
    elif pct >= 80:
        color = YELLOW
    else:
        color = GREEN
    filled = min(pct * width // 100, width)
    bar = "\u2588" * filled + "\u2591" * (width - filled)
    return f"{color}{bar}{RESET} {pct}%"


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


# ── Git ───────────────────────────────────────────
def get_git_info(cwd: str) -> str:
    try:
        subprocess.check_output(
            ["git", "rev-parse", "--git-dir"],
            cwd=cwd, stderr=subprocess.DEVNULL,
        )
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=cwd, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--numstat"],
            cwd=cwd, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        modified = subprocess.check_output(
            ["git", "diff", "--numstat"],
            cwd=cwd, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        s = len(staged.split("\n")) if staged else 0
        m = len(modified.split("\n")) if modified else 0
        parts = []
        if s:
            parts.append(f"{GREEN}+{s}{RESET}")
        if m:
            parts.append(f"{YELLOW}~{m}{RESET}")
        extra = " ".join(parts)
        return f" \u2442 {branch}" + (f" {extra}" if extra else "")
    except Exception:
        return ""


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
    new_totals, seen_ids, line_count, new_ctx = parse_jsonl(
        transcript_path, start_line, seen_ids
    )

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


# ── Main ──────────────────────────────────────────
def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        return

    # Model
    model = (data.get("model") or {}).get(
        "display_name", (data.get("model") or {}).get("id", "?")
    )

    # Workspace
    workspace = data.get("workspace") or {}
    cwd = workspace.get("current_dir") or data.get("cwd") or ""

    # Context window
    ctx = data.get("context_window") or {}
    ctx_size = ctx.get("context_window_size")

    # Session tokens from JSONL
    transcript_path = data.get("transcript_path", "")
    if transcript_path and os.path.isfile(transcript_path):
        cache = load_cache()
        totals, jsonl_ctx = get_session_totals(transcript_path, cache)
    else:
        totals = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0}
        jsonl_ctx = None

    # Context usage: prefer JSONL-derived (works for non-Anthropic models)
    if jsonl_ctx is not None:
        ctx_used = jsonl_ctx
    else:
        ctx_used = ctx.get("total_input_tokens")

    # Context percentage
    if ctx_used is not None and ctx_size is not None and ctx_size > 0:
        ctx_pct = int(ctx_used / ctx_size * 100)
    else:
        pct_raw = ctx.get("used_percentage")
        ctx_pct = int(pct_raw) if pct_raw is not None else None

    # Cost
    cost = data.get("cost") or {}
    cost_usd = cost.get("total_cost_usd") or 0
    duration_ms = cost.get("total_duration_ms") or 0
    lines_added = cost.get("total_lines_added") or 0
    lines_removed = cost.get("total_lines_removed") or 0

    # Effort & thinking
    effort = (data.get("effort") or {}).get("level")
    thinking = (data.get("thinking") or {}).get("enabled")

    # Rate limits
    rate = data.get("rate_limits") or {}
    rate_5h = (rate.get("five_hour") or {}).get("used_percentage")
    rate_7d = (rate.get("seven_day") or {}).get("used_percentage")

    # ── Build output ──────────────────────────────
    dir_name = os.path.basename(cwd) if cwd else "?"

    # Line 1: model, dir, git, effort, thinking
    line1 = f"{BOLD}{CYAN}[{model}]{RESET} \u2442 {dir_name}"
    line1 += get_git_info(cwd)
    if effort:
        line1 += f" | {DIM}effort:{RESET} {effort}"
    if thinking:
        line1 += f" | {MAGENTA}\u270a think{RESET}"

    # Line 2: progress bar + session tokens
    bar_str = progress_bar(ctx_pct if ctx_pct is not None else 0)
    total_tokens = (
        totals["input"] + totals["output"]
        + totals["cache_create"] + totals["cache_read"]
    )
    line2 = (
        f"{bar_str}"
        f" | {BOLD}In(unc):{RESET} {fmt_num(totals['input'])}"
        f" | {BOLD}Out:{RESET} {fmt_num(totals['output'])}"
        f" | {BOLD}Cache:{RESET} +{fmt_num(totals['cache_create'])}"
        f"/{fmt_num(totals['cache_read'])}"
        f" | {BOLD}Total:{RESET} {fmt_num(total_tokens)}"
    )

    # Line 3: cost, duration, code changes, rate limits
    parts = []
    parts.append(f"\u00a5 ${cost_usd:.2f}")
    if duration_ms > 0:
        parts.append(f"\u23f1\ufe0f {fmt_duration(duration_ms)}")
    if lines_added or lines_removed:
        parts.append(
            f"{GREEN}+{lines_added}{RESET} {RED}-{lines_removed}{RESET}"
        )
    if rate_5h is not None:
        parts.append(f"5h:{rate_5h:.0f}%")
    if rate_7d is not None:
        parts.append(f"7d:{rate_7d:.0f}%")
    line3 = " | ".join(parts) if parts else ""

    print(line1)
    print(line2)
    if line3:
        print(line3)


if __name__ == "__main__":
    main()
