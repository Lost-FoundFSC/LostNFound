import re
from difflib import SequenceMatcher


def _normalized_text(value):
    return ' '.join(re.sub(r'[^\w\s]', ' ', value.casefold()).split())


def _text_similarity(left, right):
    left = _normalized_text(left)
    right = _normalized_text(right)
    if not left or not right:
        return 0

    left_words = set(left.split())
    right_words = set(right.split())
    token_similarity = len(left_words & right_words) / len(left_words | right_words)
    sequence_similarity = SequenceMatcher(None, left, right).ratio()
    return max(token_similarity, sequence_similarity) * 100


def calculate_match_score(lost_report, found_report):
    """Return a comparison score from 0 to 100, not an ownership probability."""
    lost_item_words = set(_normalized_text(lost_report.item_name).split())
    found_item_words = set(_normalized_text(found_report.item_name).split())
    same_category = lost_report.category == found_report.category
    if not same_category and not lost_item_words.intersection(found_item_words):
        return 0

    weighted_scores = [
        (_text_similarity(lost_report.item_name, found_report.item_name), 60),
        (100 if same_category else 0, 20),
    ]

    if lost_report.campus_location and found_report.campus_location:
        weighted_scores.append((
            _text_similarity(lost_report.campus_location, found_report.campus_location),
            10,
        ))

    if lost_report.incident_date and found_report.incident_date:
        days_apart = abs((lost_report.incident_date - found_report.incident_date).days)
        date_similarity = (
            100 if days_apart <= 1 else
            80 if days_apart <= 7 else
            60 if days_apart <= 30 else
            35 if days_apart <= 90 else
            0
        )
        weighted_scores.append((date_similarity, 10))

    total_weight = sum(weight for _, weight in weighted_scores)
    return round(sum(score * weight for score, weight in weighted_scores) / total_weight)
