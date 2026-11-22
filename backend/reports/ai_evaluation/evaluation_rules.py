
# Passing requirements for AI matching evaluations

MIN_ACCURACY = 0.80
MIN_CONSISTENCY = 0.90

def calculate_accuracy(expected, predicted):
    """Calculate how many AI predictions are correct."""
    if not expected or len(expected) != len(predicted):
        return 0.0

    correct = sum(
        1 for a, b in zip(expected, predicted)
        if type(a) is bool and type(b) is bool and a == b
    )

    return correct / len(expected)


def check_hallucination(ai_response, valid_item_names):
    """Check whether AI mentions an item outside the supplied inventory."""
    return ai_response not in valid_item_names


def check_consistency(predictions):
    """Calculate how often the same prediction is repeated."""
    if not predictions:
        return 0.0

    most_common = max(predictions.count(p) for p in predictions)
    return most_common / len(predictions)
