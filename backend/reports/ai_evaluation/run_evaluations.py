"""Sprint 3 golden-set evaluation runner."""

import argparse
import json
import os
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

DATA_FILE = Path(__file__).with_name("golden_tests.json")


def load_golden_examples():
    with DATA_FILE.open("r", encoding="utf-8") as file:
        examples = json.load(file)

    if len(examples) < 15:
        raise ValueError("Evaluation requires at least 15 golden examples.")

    return examples


def prepare_match_inputs(example):
    """Convert one golden example into the matching service's format."""

    category_map = {
        "Bags": "Accessories",
        "Personal Items": "Other",
        "School Supplies": "Books",
        "Shoes": "Clothing",
    }

    def convert_item(item, form_id):
        category = category_map.get(item["category"], item["category"])

        return {
            "form_id": form_id,
            "item_name": item["name"],
            "category": category,
            "description": (
                f'{item["color"]}. {item["description"]}'
            ),
            "estimated_value": "",
            "incident_date": "",
            "incident_time": "",
            "campus_location": "",
            "location_details": "",
        }

    example_id = int(example["id"])

    lost = convert_item(
        example["lost_item"], f"L#{example_id:09d}"
    )

    found = convert_item(
        example["found_item"], f"F#{example_id:09d}"
    )

    return lost, [found]




def evaluate_one_example(example, mock=False):
    """Evaluate one example through the existing matching service."""
    from matching.services import find_matches

    lost, found = prepare_match_inputs(example)


    if mock:
        # Simulated predictions, not real Claude performance results.
        simulated_score = 95 if example["expected_match"] else 15

        simulated_response = json.dumps({
            "matches": [
                {
                    "form_id": found[0]["form_id"],
                    "score": simulated_score,
                    "reason": "Simulated matching evaluation response."
                }
            ]
        })

        with patch(
            "matching.services._call_claude",
            return_value=simulated_response
        ):
            result = find_matches(lost, found)

    else:
        result = find_matches(lost, found)

    expected = example["expected_match"]

    predicted = any(
        match["form_id"] == found[0]["form_id"]
        and match["score"] >= 60
        for match in result["matches"]
    )

    return {
        "example_id": example["id"],
        "expected_match": expected,
        "predicted_match": predicted,
        "correct": expected == predicted,
        "source": result["source"],
        "matches": result["matches"],
    }



def evaluate_consistency(example, mock=False, repetitions=3):
    """Measure whether repeated runs produce the same match decision."""
    from evaluation_rules import check_consistency

    predictions = []

    for _ in range(repetitions):
        result = evaluate_one_example(example, mock=mock)

        # A fallback must not count as a successful live Claude run.
        if not mock and result["source"] != "claude":
            raise RuntimeError(
                f'Claude failed during consistency evaluation '
                f'for example {example["id"]}'
            )

        predictions.append(result["predicted_match"])

    return check_consistency(predictions)



def evaluate_hallucination(example):
    """Verify invented report IDs are rejected by the matching service."""
    from matching.services import find_matches

    lost, found = prepare_match_inputs(example)
    invented_id = "F#999999999"

    simulated_response = json.dumps({
        "matches": [
            {
                "form_id": invented_id,
                "score": 99,
                "reason": "Invented report ID."
            }
        ]
    })

    with patch(
        "matching.services._call_claude",
        return_value=simulated_response
    ):
        result = find_matches(lost, found)

    valid_ids = {item["form_id"] for item in found}

    return all(
        match["form_id"] in valid_ids
        for match in result["matches"]
    )



def main():
    parser = argparse.ArgumentParser(
        description="Run LostNFound AI matching evaluations."
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--mock",
        action="store_true",
        help="Run evaluations without real Claude API calls.",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help="Run evaluations against the real Claude API.",
    )

    args = parser.parse_args()

    examples = load_golden_examples()
    print(f"Loaded {len(examples)} golden evaluation examples.")

    if args.mock:
        print("Mode: MOCK — no real Claude API calls.\n")

        results = [
            evaluate_one_example(example, mock=True)
            for example in examples
        ]

        for result in results:
            status = "PASS" if result["correct"] else "FAIL"
            print(f'Example {result["example_id"]:02d}: {status}')

        correct = sum(result["correct"] for result in results)
        accuracy = correct / len(results)

        print(f"\nMock fixture checks: {correct}/{len(results)}")
        print(f"Fixture agreement: {accuracy:.1%}")

        consistency_scores = [
            evaluate_consistency(example, mock=True)
            for example in examples
        ]

        average_consistency = (
            sum(consistency_scores) / len(consistency_scores)
        )

        print("\nConsistency Evaluation")
        print(f"Examples evaluated: {len(consistency_scores)}")
        print("Repeated runs per example: 3")
        print(f"Average consistency: {average_consistency:.1%}")



        hallucination_results = [
            evaluate_hallucination(example)
            for example in examples
        ]

        passed = sum(hallucination_results)

        print("\nHallucination Protection")
        print(f"Invented ID rejection: {passed}/{len(examples)}")

        # Enforce Sprint 3 evaluation thresholds.
        from evaluation_rules import MIN_ACCURACY, MIN_CONSISTENCY

        protection_rate = passed / len(examples)

        checks = {
            "Fixture agreement": (accuracy, MIN_ACCURACY),
            "Consistency": (average_consistency, MIN_CONSISTENCY),
            "Invented-ID rejection": (protection_rate, 1.0),
        }

        print("\nThreshold Results")
        failed = False

        for name, (actual, minimum) in checks.items():
            success = actual >= minimum
            status = "PASS" if success else "FAIL"

            print(
                f"{name}: {actual:.1%} "
                f"(minimum {minimum:.1%}) — {status}"
            )

            if not success:
                failed = True

        if failed:
            raise SystemExit(1)


        return


    print("Mode: LIVE — using the Claude API.\n")

    results = []

    for example in examples:
        result = evaluate_one_example(example)
        results.append(result)

        status = "PASS" if result["correct"] else "FAIL"

        print(
            f'Example {result["example_id"]:02d}: {status} '
            f'| Expected: {result["expected_match"]} '
            f'| Predicted: {result["predicted_match"]} '
            f'| Source: {result["source"]}'
        )

    correct = sum(result["correct"] for result in results)
    accuracy = correct / len(results)

    print("\nEvaluation Summary")
    print(f"Correct predictions: {correct}/{len(results)}")
    print(f"Accuracy: {accuracy:.1%}")
    print(
        "Non-Claude responses:",
        sum(result["source"] != "claude" for result in results)
    )



if __name__ == "__main__":


    main()