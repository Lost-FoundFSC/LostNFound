
import json
import unittest
from pathlib import Path


# Location of our golden test examples
DATA_FILE = Path(__file__).with_name("golden_tests.json")


class AIEvaluationTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with DATA_FILE.open("r", encoding="utf-8") as file:
            cls.examples = json.load(file)

    def test_has_15_examples(self):
        # Check that we created exactly 15 examples
        self.assertEqual(len(self.examples), 15)

    def test_unique_ids(self):
        # Each example should have its own ID
        ids = [example["id"] for example in self.examples]
        self.assertEqual(len(ids), len(set(ids)))

    def test_required_fields(self):
        # Check that each example contains the needed fields
        required = {"name", "category", "color", "description"}

        for example in self.examples:
            with self.subTest(example=example["id"]):
                for item_type in ("lost_item", "found_item"):
                    item = example[item_type]
                    self.assertTrue(required.issubset(item))
                    for field in required:
                        self.assertIsInstance(item[field], str)
                        self.assertTrue(item[field].strip())

    def test_expected_match_values(self):
        # Expected matches must be True or False
        for example in self.examples:
            with self.subTest(example=example["id"]):
                self.assertIsInstance(example["expected_match"], bool)

    def test_positive_and_negative_examples(self):
        # Include both matching and non-matching items
        results = [example["expected_match"] for example in self.examples]
        self.assertIn(True, results)
        self.assertIn(False, results)


    def test_accuracy_calculation(self):
        from evaluation_rules import calculate_accuracy

        expected = [True, False, True, False, True]
        predicted = [True, False, True, True, True]

        accuracy = calculate_accuracy(expected, predicted)
        self.assertEqual(accuracy, 0.80)

    def test_hallucination_detection(self):
        from evaluation_rules import check_hallucination

        valid_items = ["AirPods", "Backpack", "Laptop"]

        self.assertFalse(
            check_hallucination("AirPods", valid_items)
        )

        self.assertTrue(
            check_hallucination("iPhone", valid_items)
        )

    def test_consistency_calculation(self):
        from evaluation_rules import check_consistency

        predictions = [True, True, True, True, False]

        consistency = check_consistency(predictions)
        self.assertEqual(consistency, 0.80)

    def test_passing_thresholds(self):
        from evaluation_rules import MIN_ACCURACY, MIN_CONSISTENCY

        self.assertEqual(MIN_ACCURACY, 0.80)
        self.assertEqual(MIN_CONSISTENCY, 0.90)



if __name__ == "__main__":
    unittest.main()
