"""Finding reports by form ID, matching lost and found reports, and moving
reports in and out of the archive."""
from django.db import transaction
from django.utils import timezone

from .models import (
    COPIED_FIELDS, DONE_STATUSES, OPEN_STATUSES, ArchivedReport,
    ArchivedReportImage, FoundReport, FoundReportImage, LostReport,
    LostReportImage, ReportStatus, ReportType, normalize_form_id, semester_for,
)

OPEN_MODELS = {ReportType.LOST: LostReport, ReportType.FOUND: FoundReport}
OPEN_IMAGE_MODELS = {ReportType.LOST: LostReportImage, ReportType.FOUND: FoundReportImage}
TYPE_BY_PREFIX = {'L': ReportType.LOST, 'F': ReportType.FOUND}


def find_report(form_id):
    """Return the open or archived report with this form ID, or None."""
    form_id = normalize_form_id(form_id)
    if form_id is None:
        return None
    model = OPEN_MODELS[TYPE_BY_PREFIX[form_id[0]]]
    return (
        model.objects.prefetch_related('images').filter(form_id=form_id).first()
        or ArchivedReport.objects.prefetch_related('images').filter(form_id=form_id).first()
    )


def reports_for_email(email):
    """All reports (open and archived) submitted with this email, newest first."""
    reports = []
    for model in (LostReport, FoundReport, ArchivedReport):
        reports.extend(model.objects.filter(email__iexact=email))
    return sorted(reports, key=lambda report: report.created_at, reverse=True)


def _copy_fields(report):
    return {name: getattr(report, name) for name in COPIED_FIELDS}


@transaction.atomic
def archive_report(report, status):
    """Move an open report into the archive with a final status."""
    assert status in DONE_STATUSES
    now = timezone.now()
    archived = ArchivedReport.objects.create(
        report_type=report.REPORT_TYPE,
        status=status,
        completed_at=now,
        archive_semester=semester_for(timezone.localtime(now)),
        **_copy_fields(report),
    )
    for image in report.images.all():
        # Point at the same file on disk; nothing is copied.
        ArchivedReportImage.objects.create(
            report=archived, image=image.image.name, uploaded_at=image.uploaded_at,
        )
    report.delete()
    return archived


@transaction.atomic
def restore_report(archived, status):
    """Move an archived report back to the open lost/found table."""
    assert status in OPEN_STATUSES
    model = OPEN_MODELS[archived.report_type]
    image_model = OPEN_IMAGE_MODELS[archived.report_type]
    report = model.objects.create(status=status, **_copy_fields(archived))
    for image in archived.images.all():
        image_model.objects.create(
            report=report, image=image.image.name, uploaded_at=image.uploaded_at,
        )
    archived.delete()
    return report


# ----------------------------------------------------------------- matching

class MatchError(ValueError):
    """A lost/found match that is not allowed. The message is shown to the user."""


def check_match(report, other_form_id):
    """Validate a match without saving it. Returns the other report."""
    other_id = normalize_form_id(other_form_id)
    if other_id is None:
        raise MatchError('Enter a form ID like L#123456789 or F#123456789.')
    if other_id == report.form_id:
        raise MatchError("A report can't be matched to itself.")
    if other_id[0] == report.form_id[0]:
        raise MatchError('A lost report can only be matched to a found report, and a found report to a lost one.')
    other = find_report(other_id)
    if other is None:
        raise MatchError(f'There is no report with form ID {other_id}.')
    if report.matched_form_id and report.matched_form_id != other.form_id:
        raise MatchError(f'{report.form_id} is already matched to {report.matched_form_id}. Remove that match first.')
    if other.matched_form_id and other.matched_form_id != report.form_id:
        raise MatchError(f'{other.form_id} is already matched to {other.matched_form_id}.')
    return other


def _set_match(report, form_id):
    report.matched_form_id = form_id
    report.save(update_fields=['matched_form_id', 'updated_at'])


@transaction.atomic
def match_reports(report, other_form_id):
    """Link a lost report and a found report so each stores the other's form ID."""
    other = check_match(report, other_form_id)
    _set_match(report, other.form_id)
    _set_match(other, report.form_id)
    return other


@transaction.atomic
def unmatch_report(report):
    """Remove a match from both reports."""
    if not report.matched_form_id:
        return
    other = find_report(report.matched_form_id)
    if other is not None and other.matched_form_id == report.form_id:
        _set_match(other, '')
    _set_match(report, '')


# ------------------------------------------------------------------ status

def _apply_status(report, status):
    is_archived = isinstance(report, ArchivedReport)
    if status in DONE_STATUSES:
        if is_archived:
            report.status = status
            report.save(update_fields=['status', 'updated_at'])
            return report
        return archive_report(report, status)

    if is_archived:
        return restore_report(report, status)
    report.status = status
    report.save(update_fields=['status', 'updated_at'])
    return report


@transaction.atomic
def change_status(report, status):
    """Set a new status, archiving or restoring the report when needed.

    Matched reports share their return: marking one Returned also marks its
    match Returned (both move to the archive), and reopening a returned report
    also reopens its returned match.

    Returns the report as it now exists (it may be a different object).
    """
    was_returned = isinstance(report, ArchivedReport) and report.status == ReportStatus.RETURNED
    partner = find_report(report.matched_form_id) if report.matched_form_id else None

    updated = _apply_status(report, status)

    if partner is not None:
        if status == ReportStatus.RETURNED and partner.status != ReportStatus.RETURNED:
            _apply_status(partner, ReportStatus.RETURNED)
        elif (was_returned and status in OPEN_STATUSES
              and isinstance(partner, ArchivedReport) and partner.status == ReportStatus.RETURNED):
            _apply_status(partner, status)
    return updated
