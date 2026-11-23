"""Run with: py manage.py test matching
Claude is faked (mocked), so these never use the API key or cost money.

Field names match backend/reports/models.py.
"""
import os
import unittest
from unittest.mock import patch

from .services import find_matches

LOST = {
    "form_id": "L#384834901", "category": "Accessories",
    "item_name": "North Face backpack",
    "description": "black backpack with a red keychain on the zipper, laptop inside",
    "estimated_value": "80.00", "incident_date": "2026-11-10",
    "incident_time": "14:30:00", "campus_location": "Greenley Library",
    "location_details": "second floor study area",
}

FOUND = [
    {"form_id": "F#238832420", "category": "Accessories",
     "item_name": "Black backpack",
     "description": "black backpack turned in, red keychain attached, laptop inside",
     "estimated_value": "", "incident_date": "2026-11-11",
     "incident_time": "", "campus_location": "Greenley Library",
     "location_details": "front desk"},
    {"form_id": "F#111111111", "category": "Electronics",
     "item_name": "Blue water bottle",
     "description": "blue hydro flask with stickers, dent on the bottom",
     "estimated_value": "", "incident_date": "2026-11-11",
     "incident_time": "", "campus_location": "Nold Hall",
     "location_details": ""},
]

CALL = "matching.services._call_claude"


class ClaudeWorksTests(unittest.TestCase):
    @patch(CALL, return_value='{"matches": [{"form_id": "F#238832420", "score": 92, '
                              '"reason": "Same keychain and colour, same building."}]}')
    def test_good_json_is_used(self, _):
        result = find_matches(LOST, FOUND)
        self.assertEqual(result["source"], "claude")
        self.assertEqual(result["matches"][0]["form_id"], "F#238832420")
        self.assertEqual(result["matches"][0]["score"], 92)

    @patch(CALL, return_value='```json\n{"matches": [{"form_id": "F#238832420", "score": 80, "reason": "x"}]}\n```')
    def test_json_in_code_fence_still_works(self, _):
        self.assertEqual(find_matches(LOST, FOUND)["source"], "claude")

    @patch(CALL, return_value='{"matches": [{"form_id": "F#999999999", "score": 95, "reason": "made up"}]}')
    def test_made_up_report_is_dropped(self, _):
        self.assertEqual(find_matches(LOST, FOUND)["matches"], [])

    @patch(CALL, return_value='{"matches": [{"form_id": "f#238832420", "score": 70, "reason": "lowercase id"}]}')
    def test_lowercase_form_id_is_accepted(self, _):
        self.assertEqual(find_matches(LOST, FOUND)["matches"][0]["form_id"], "F#238832420")

    @patch(CALL, return_value='{"matches": [{"form_id": "F#238832420", "score": 500, "reason": "x"}]}')
    def test_score_is_capped_at_100(self, _):
        self.assertEqual(find_matches(LOST, FOUND)["matches"][0]["score"], 100)


class FallbackTests(unittest.TestCase):
    @patch(CALL, return_value="Sure! Here are the matches you asked for.")
    def test_bad_json_uses_fallback(self, _):
        self.assertEqual(find_matches(LOST, FOUND)["source"], "fallback")

    @patch(CALL, side_effect=TimeoutError("too slow"))
    def test_timeout_uses_fallback(self, _):
        self.assertEqual(find_matches(LOST, FOUND)["source"], "fallback")

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_api_key_uses_fallback(self):
        self.assertEqual(find_matches(LOST, FOUND)["source"], "fallback")

    @patch(CALL, side_effect=ConnectionError("no wifi"))
    def test_fallback_ranks_the_right_item_first(self, _):
        result = find_matches(LOST, FOUND)
        self.assertEqual(result["matches"][0]["form_id"], "F#238832420")
        self.assertTrue(all(m["form_id"] != "F#111111111" for m in result["matches"]))

    def test_no_candidates_returns_empty(self):
        self.assertEqual(find_matches(LOST, [])["matches"], [])

    @patch(CALL, side_effect=ConnectionError)
    def test_only_15_items_sent(self, mock_call):
        many = [dict(FOUND[0], form_id=f"F#20000000{i}") for i in range(40)]
        find_matches(LOST, many)
        self.assertEqual(len(mock_call.call_args[0][1]), 15)


if __name__ == "__main__":
    unittest.main()
