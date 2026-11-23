"""Main entry point: find_matches(lost, found_reports).

Tries Claude first. If anything goes wrong (no key, no internet, timeout,
bad JSON) it uses the backup scorer instead. Output looks the same either way:

{"source": "claude" | "fallback",
 "prompt_version": "v2",
 "matches": [{"form_id": "F#238832420", "score": 87, "reason": "..."}]}

Field names match backend/reports/models.py.
"""
import json
import logging
import os

from .fallback import fallback_match
from .prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_message

log = logging.getLogger(__name__)

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
MAX_CANDIDATES = 15     # never send more than this many found reports to Claude
TIMEOUT_SECONDS = 10
MIN_SCORE_TO_SHOW = 30  # hide very weak matches


def _call_claude(lost, found_items):
    """Ask Claude. Returns its raw text. Raises an exception on any problem."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or api_key.startswith("paste-your"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    import anthropic  # imported here so tests/CI work without the package
    client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SECONDS)
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        temperature=0,  # makes results more consistent run to run
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message(lost, found_items)}],
    )
    return response.content[0].text


def _parse_and_check(raw_text, found_items):
    """Turn Claude's text into a clean list. Raises ValueError if it's junk.

    This is our protection against bad AI output: we never trust it blindly.
    """
    text = raw_text.strip()
    if text.startswith("```"):  # Claude sometimes wraps JSON in ``` fences
        text = text.strip("`").removeprefix("json").strip()
    data = json.loads(text)  # raises ValueError if not JSON

    valid_ids = {f["form_id"] for f in found_items}
    clean = []
    for m in data["matches"]:
        fid = str(m["form_id"]).strip().upper()
        if fid not in valid_ids:
            continue  # Claude made up a report -> drop it
        score = max(0, min(100, int(m["score"])))
        reason = str(m.get("reason", ""))[:300]
        clean.append({"form_id": fid, "score": score, "reason": reason})
    return clean


def find_matches(lost, found_reports):
    """lost: dict for one lost report. found_reports: list of dicts, each with 'form_id'."""
    candidates = list(found_reports)[:MAX_CANDIDATES]
    if not candidates:
        return {"source": "none", "prompt_version": PROMPT_VERSION, "matches": []}

    try:
        raw = _call_claude(lost, candidates)
        matches = _parse_and_check(raw, candidates)
        source = "claude"
    except Exception as exc:  # any failure -> backup scorer
        log.warning("Claude matching failed, using fallback: %s", exc)
        matches = fallback_match(lost, candidates)
        source = "fallback"

    matches = [m for m in matches if m["score"] >= MIN_SCORE_TO_SHOW]
    matches.sort(key=lambda m: m["score"], reverse=True)
    return {"source": source, "prompt_version": PROMPT_VERSION, "matches": matches}
