"""API endpoint: POST /api/match/

Body (JSON): {"form_id": "L#384834901"}   <- a lost report's form ID
Response:    {"source": "claude", "prompt_version": "v2",
              "matches": [{"form_id": "F#238832420", "score": 87, "reason": "..."}]}

Pulls the candidates straight from Matthew's FoundReport table.
"""
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from reports.models import FoundReport, LostReport

from .services import find_matches

# Only these fields go to Claude. Keep it small: cost and latency matter.
REPORT_FIELDS = (
    "form_id", "category", "item_name", "description", "estimated_value",
    "incident_date", "incident_time", "campus_location", "location_details",
)


def _as_dict(report):
    data = {name: getattr(report, name) for name in REPORT_FIELDS}
    # Decimals/dates aren't JSON-friendly; send them as text.
    data["estimated_value"] = str(data["estimated_value"] or "")
    for key in ("incident_date", "incident_time"):
        data[key] = str(data[key] or "")
    return data


@csrf_exempt  # TODO: remove once React sends the CSRF token
@require_POST
def match_view(request):
    try:
        body = json.loads(request.body)
        lost = LostReport.objects.get(form_id=body["form_id"])
    except (ValueError, KeyError):
        return JsonResponse({"error": "Send JSON with a 'form_id' field"}, status=400)
    except LostReport.DoesNotExist:
        return JsonResponse({"error": "No lost report with that form ID"}, status=404)

    lost_data = _as_dict(lost)

    # Candidate filter: same category, and found on or after the lost date.
    # This is what keeps the list short before Claude sees anything.
    candidates = FoundReport.objects.filter(category=lost.category)
    if lost.incident_date:
        candidates = candidates.filter(
            incident_date__isnull=False,
            incident_date__gte=lost.incident_date,
        )
    candidates = candidates[:15]  # MAX_CANDIDATES in services.py

    found_data = [_as_dict(r) for r in candidates]
    result = find_matches(lost_data, found_data)
    result["lost_form_id"] = lost.form_id
    return JsonResponse(result)
