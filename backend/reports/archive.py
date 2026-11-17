"""Finding reports by form ID and moving them in and out of the archive."""
from django.db import transaction
from django.utils import timezone

from .models import (
    COPIED_FIELDS, DONE_STATUSES, OPEN_STATUSES, ArchivedReport,
    ArchivedReportImage, FoundReport, FoundReportImage, LostReport,
    LostReportImage, ReportType, normalize_form_id, semester_for,
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


def change_status(report, status):
    """Set a new status, archiving or restoring the report when needed.

    Returns the report as it now exists (it may be a different object).
    """
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
