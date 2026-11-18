import os
import re
import secrets
from uuid import uuid4

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Category(models.TextChoices):
    # Value and label are the same, so the admin shows them exactly as the form does.
    ELECTRONICS = 'Electronics', 'Electronics'
    CLOTHING = 'Clothing', 'Clothing'
    ACCESSORIES = 'Accessories', 'Accessories'
    WALLETS_IDS = 'Wallets & IDs', 'Wallets & IDs'
    BOOKS = 'Books', 'Books'
    OTHER = 'Other', 'Other'


class ReportType(models.TextChoices):
    LOST = 'lost'
    FOUND = 'found'


class ReportStatus(models.TextChoices):
    """Same stages as REPORT_STAGES in frontend/src/data/accountDemoData.js."""

    # Open: report stays in the lost/found tables.
    REPORTED = 'reported', 'Reported'
    POSSIBLE_MATCH = 'possible_match', 'Possible match'
    UNDER_VERIFICATION = 'under_verification', 'Under verification'
    READY_FOR_PICKUP = 'ready_for_pickup', 'Ready for pickup'
    # Done: report is moved to the archive.
    RETURNED = 'returned', 'Returned'
    CLOSED = 'closed', 'Closed'
    CANCELLED = 'cancelled', 'Cancelled'


OPEN_STATUSES = [
    ReportStatus.REPORTED, ReportStatus.POSSIBLE_MATCH,
    ReportStatus.UNDER_VERIFICATION, ReportStatus.READY_FOR_PICKUP,
]
DONE_STATUSES = [ReportStatus.RETURNED, ReportStatus.CLOSED, ReportStatus.CANCELLED]
OPEN_STATUS_CHOICES = [(s.value, s.label) for s in OPEN_STATUSES]
DONE_STATUS_CHOICES = [(s.value, s.label) for s in DONE_STATUSES]


# ---------------------------------------------------------------- form IDs

FORM_ID_PREFIX = {ReportType.LOST: 'L', ReportType.FOUND: 'F'}
FORM_ID_PATTERN = re.compile(r'^([LF])#?(\d{9})$')


def normalize_form_id(value):
    """'l384834901', 'L#384834901' -> 'L#384834901'. Returns None if invalid."""
    match = FORM_ID_PATTERN.match(str(value or '').strip().upper())
    if not match:
        return None
    return f'{match.group(1)}#{match.group(2)}'


def generate_form_id(report_type):
    """Random, unique ID such as L#384834901 or F#238832420."""
    prefix = FORM_ID_PREFIX[report_type]
    while True:
        form_id = f'{prefix}#{secrets.randbelow(900_000_000) + 100_000_000}'
        if not form_id_exists(form_id):
            return form_id


def form_id_exists(form_id):
    return (
        LostReport.objects.filter(form_id=form_id).exists()
        or FoundReport.objects.filter(form_id=form_id).exists()
        or ArchivedReport.objects.filter(form_id=form_id).exists()
    )


def semester_for(date):
    if date.month <= 5:
        return f'Spring {date.year}'
    if date.month <= 8:
        return f'Summer {date.year}'
    return f'Fall {date.year}'


# ----------------------------------------------------------------- reports

class ReportFields(models.Model):
    """What the person filled in on the form (mirrors frontend REPORT_FIELDS)."""

    form_id = models.CharField(max_length=11, unique=True, editable=False)

    # Contact. Required on lost reports (security has to reach the owner).
    # Optional on found reports: the finder has handed the item in, so
    # everything they know is already on the form.
    full_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(max_length=150, blank=True)
    student_id = models.CharField(max_length=9, blank=True)  # full RAM ID
    phone = models.CharField(max_length=25, blank=True)

    # Item
    category = models.CharField(max_length=30, choices=Category.choices)
    item_name = models.CharField(max_length=120)
    description = models.TextField(max_length=1500)
    estimated_value = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )

    # When / where. Optional: the person may not know exactly, so these
    # can be left blank or be a best guess.
    incident_date = models.DateField(null=True, blank=True)
    incident_time = models.TimeField(null=True, blank=True)
    campus_location = models.CharField(max_length=100, blank=True)
    location_details = models.TextField(max_length=1000, blank=True)

    # Map pin. Reserved for the upcoming campus map feature: optional and
    # empty until the map is added to the form. Both are set or neither.
    map_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    map_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )

    liability_accepted = models.BooleanField(default=False)

    # Form ID of the report on the other side of a confirmed match: a lost
    # report's found report, or the other way around. Set by Campus Security.
    # Both reports always point at each other, open or archived.
    matched_form_id = models.CharField(
        'Matched form ID', max_length=11, blank=True,
        help_text='Form ID of the matching lost or found report, like F#123456789. '
                  'Saving links both reports. Clear it to remove the match.',
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.form_id} {self.item_name}'


# Field names copied when a report moves to or from the archive.
COPIED_FIELDS = [
    'form_id', 'full_name', 'email', 'student_id', 'phone', 'category',
    'item_name', 'description', 'estimated_value', 'incident_date',
    'incident_time', 'campus_location', 'location_details',
    'map_latitude', 'map_longitude',
    'liability_accepted', 'matched_form_id', 'created_at',
]


class OpenReport(ReportFields):
    """A report still being worked on."""

    REPORT_TYPE = None  # set by subclasses

    status = models.CharField(
        max_length=20, choices=OPEN_STATUS_CHOICES, default=ReportStatus.REPORTED,
    )

    class Meta(ReportFields.Meta):
        abstract = True

    @property
    def report_type(self):
        return self.REPORT_TYPE

    is_active = True
    completed_at = None
    archive_semester = None

    def save(self, *args, **kwargs):
        if not self.form_id:
            self.form_id = generate_form_id(self.REPORT_TYPE)
        super().save(*args, **kwargs)


class LostReport(OpenReport):
    """Submitted by someone who lost an item. Form IDs start with L#."""

    REPORT_TYPE = ReportType.LOST


class FoundReport(OpenReport):
    """Submitted by someone who found an item. Form IDs start with F#."""

    REPORT_TYPE = ReportType.FOUND


class ArchivedReport(ReportFields):
    """A finished report (returned, closed, or cancelled).

    Kept out of the lost/found tables so matching only looks at open reports.
    """

    report_type = models.CharField(max_length=5, choices=ReportType.choices)
    status = models.CharField(max_length=20, choices=DONE_STATUS_CHOICES)
    completed_at = models.DateTimeField()
    archive_semester = models.CharField(max_length=20)  # e.g. "Fall 2026"

    is_active = False

    class Meta(ReportFields.Meta):
        ordering = ['-completed_at']


# ------------------------------------------------------------------ photos

def report_image_path(instance, filename):
    """Store photos under a random name so original file names are not kept."""
    ext = os.path.splitext(filename)[1].lower()
    return f'report_images/{instance.REPORT_TYPE}/{uuid4().hex}{ext}'


class ReportImageBase(models.Model):
    image = models.ImageField(upload_to=report_image_path)
    uploaded_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        abstract = True
        ordering = ['uploaded_at', 'id']

    def __str__(self):
        return os.path.basename(self.image.name)


class LostReportImage(ReportImageBase):
    REPORT_TYPE = ReportType.LOST
    report = models.ForeignKey(LostReport, on_delete=models.CASCADE, related_name='images')


class FoundReportImage(ReportImageBase):
    REPORT_TYPE = ReportType.FOUND
    report = models.ForeignKey(FoundReport, on_delete=models.CASCADE, related_name='images')


class ArchivedReportImage(ReportImageBase):
    REPORT_TYPE = 'archive'  # files keep their original lost/found folder
    report = models.ForeignKey(ArchivedReport, on_delete=models.CASCADE, related_name='images')
