"""Backup scorer used when Claude is unavailable. No AI, no internet needed.

Field names match backend/reports/models.py. There is no colour or brand
column in the database, so those are picked out of the description text.
"""
import re
from datetime import date, datetime

STOPWORDS = {"a", "an", "the", "and", "or", "of", "in", "on", "with", "my", "it",
             "is", "was", "near", "at", "to", "has", "have", "i", "left", "found"}

# How many points each signal is worth (adds up to 100)
WEIGHTS = {"category": 25, "location": 15, "item_name": 20, "text": 40}

COLORS = {"black", "white", "gray", "grey", "silver", "red", "blue", "green",
          "yellow", "orange", "purple", "pink", "brown", "tan", "beige", "gold",
          "navy", "maroon", "teal", "clear"}


def _words(*parts):
    text = " ".join(str(p or "") for p in parts).lower()
    return {w for w in re.findall(r"[a-z0-9]+", text) if w not in STOPWORDS}


def _same(a, b):
    return bool(a) and bool(b) and str(a).strip().lower() == str(b).strip().lower()


def _to_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)).date()
    except (TypeError, ValueError):
        return None


def _campus_location(report):
    return report.get("campus_location") or ""


def score_pair(lost, found):
    """Return (score 0-100, reason) for one lost/found report pair."""
    points, hits = 0, []

    if _same(lost.get("category"), found.get("category")):
        points += WEIGHTS["category"]; hits.append("category")

    if _words(_campus_location(lost)) & _words(_campus_location(found)):
        points += WEIGHTS["location"]; hits.append("location")

    lost_name, found_name = _words(lost.get("item_name")), _words(found.get("item_name"))
    if lost_name and found_name:
        name_overlap = len(lost_name & found_name) / len(lost_name | found_name)
        points += round(WEIGHTS["item_name"] * name_overlap)
        if name_overlap > 0.4:
            hits.append("item name")

    lost_text = _words(lost.get("description"), lost.get("location_details"))
    found_text = _words(found.get("description"), found.get("location_details"))
    if lost_text and found_text:
        overlap = len(lost_text & found_text) / len(lost_text | found_text)
        points += round(WEIGHTS["text"] * overlap)
        if overlap > 0.15:
            hits.append("description")

    # Colour words are a strong signal and live inside the description.
    shared_colors = (lost_text & found_text) & COLORS
    if shared_colors:
        points += 10
        hits.append("colour (" + ", ".join(sorted(shared_colors)) + ")")

    lost_d, found_d = _to_date(lost.get("incident_date")), _to_date(found.get("incident_date"))
    if lost_d and found_d and found_d < lost_d:
        points = points // 4
        hits.append("but found before it was lost")

    reason = ("Matches on " + ", ".join(hits)) if hits else "Few details in common"
    return min(points, 100), reason + " (backup scorer)."


def fallback_match(lost, found_items):
    results = []
    for f in found_items:
        score, reason = score_pair(lost, f)
        results.append({"form_id": f["form_id"], "score": score, "reason": reason})
    return sorted(results, key=lambda r: r["score"], reverse=True)
