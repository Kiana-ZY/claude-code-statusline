#!/usr/bin/env python3
"""Token helper: parse JSONL transcript, return token totals + context usage.
Called by statusline.sh for incremental JSONL parsing with caching."""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CACHE_PATH = os.path.expanduser("~/.claude/scripts/token_cache.json")


def load_cache():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache):
    tmp = CACHE_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, separators=(",", ":"))
        os.replace(tmp, CACHE_PATH)
    except Exception:
        pass


def parse_jsonl(path, start_line, seen_ids):
    totals = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0}
    last_ctx = None
    if not os.path.isfile(path):
        return totals, seen_ids, 0, last_ctx

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
                u = msg["usage"]
                totals["input"] += u.get("input_tokens", 0)
                totals["output"] += u.get("output_tokens", 0)
                totals["cache_create"] += u.get("cache_creation_input_tokens", 0)
                totals["cache_read"] += u.get("cache_read_input_tokens", 0)
                if mid:
                    seen_ids.add(mid)
                last_ctx = (
                    u.get("input_tokens", 0)
                    + u.get("cache_read_input_tokens", 0)
                    + u.get("cache_creation_input_tokens", 0)
                )
    except Exception:
        pass
    return totals, seen_ids, lc, last_ctx


def get_session_totals(transcript_path, cache):
    # Normalize path separators to avoid duplicate cache entries
    transcript_path = transcript_path.replace("\\", "/")
    entry = cache.get(transcript_path, {})
    cached = entry.get("totals", {})
    seen_ids = set(entry.get("seen_ids", []))
    prev_lc = entry.get("lc", 0)
    last_ctx = entry.get("last_ctx")

    try:
        fsize = os.path.getsize(transcript_path)
    except OSError:
        fsize = 0

    if entry and entry.get("fsize") == fsize and cached:
        return cached, last_ctx

    start = prev_lc + 1 if prev_lc > 0 else 1
    new_totals, seen_ids, lc, new_ctx = parse_jsonl(transcript_path, start, seen_ids)

    totals = {
        "input": cached.get("input", 0) + new_totals["input"],
        "output": cached.get("output", 0) + new_totals["output"],
        "cache_create": cached.get("cache_create", 0) + new_totals["cache_create"],
        "cache_read": cached.get("cache_read", 0) + new_totals["cache_read"],
    }
    if new_ctx is not None:
        last_ctx = new_ctx

    cache[transcript_path] = {
        "lc": lc, "fsize": fsize,
        "seen_ids": list(seen_ids),
        "totals": totals, "last_ctx": last_ctx,
    }
    save_cache(cache)
    return totals, last_ctx


def fmt(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def main():
    if len(sys.argv) < 2:
        sys.exit(0)
    transcript_path = sys.argv[1]
    ctx_size = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    # current_usage from stdin JSON (more accurate than JSONL for context)
    cur_input = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    cur_cache_read = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    cur_cache_create = int(sys.argv[5]) if len(sys.argv) > 5 else 0

    if not transcript_path or not os.path.isfile(transcript_path):
        # Output empty tokens, but still use current_usage for context
        ctx_used = cur_input + cur_cache_read + cur_cache_create
        ctx_pct = int(ctx_used / ctx_size * 100) if ctx_size > 0 else 0
        print(json.dumps({"in": "0", "out": "0", "cache_cr": "0", "cache_rd": "0",
                          "total": "0", "ctx_used": fmt(ctx_used), "ctx_size": fmt(ctx_size), "ctx_pct": str(ctx_pct)}))
        sys.exit(0)

    cache = load_cache()
    totals, last_ctx = get_session_totals(transcript_path, cache)

    total = totals["input"] + totals["output"] + totals["cache_create"] + totals["cache_read"]

    # Context: prefer current_usage from stdin (matches /context command),
    # fallback to JSONL last_ctx, then 0
    ctx_used = cur_input + cur_cache_read + cur_cache_create
    if ctx_used == 0:
        ctx_used = last_ctx or 0
    ctx_pct = int(ctx_used / ctx_size * 100) if ctx_size > 0 else 0

    print(json.dumps({
        "in": fmt(totals["input"]),
        "out": fmt(totals["output"]),
        "cache_cr": fmt(totals["cache_create"]),
        "cache_rd": fmt(totals["cache_read"]),
        "total": fmt(total),
        "ctx_used": fmt(ctx_used),
        "ctx_size": fmt(ctx_size),
        "ctx_pct": str(ctx_pct),
    }))


if __name__ == "__main__":
    main()
