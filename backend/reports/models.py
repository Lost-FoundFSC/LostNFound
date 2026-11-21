from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        CAMPUS_SECURITY = 'campus_security', 'Campus Security'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lost_found_profile',
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    full_name = models.CharField(max_length=100)
    ram_id = models.CharField(max_length=9, blank=True)
    student_id = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=25, blank=True)

    def clean(self):
        if self.ram_id:
            import re
            if not re.fullmatch(r'R\d{8}', self.ram_id.upper()):
                raise ValidationError({'ram_id': 'RAM ID must be R followed by 8 digits.'})

    def save(self, *args, **kwargs):
        if self.ram_id:
            self.ram_id = self.ram_id.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.full_name} ({self.get_role_display()})'


class Report(models.Model):
    class ReportType(models.TextChoices):
        LOST = 'lost', 'Lost'
        FOUND = 'found', 'Found'

    class Status(models.TextChoices):
        REPORTED = 'reported', 'Reported'
        POSSIBLE_MATCH = 'possible_match', 'Possible match'
        UNDER_VERIFICATION = 'under_verification', 'Under verification'
        READY_FOR_PICKUP = 'ready_for_pickup', 'Ready for pickup'
        RETURNED = 'returned', 'Returned'
        CLOSED = 'closed', 'Closed'
        CANCELLED = 'cancelled', 'Cancelled'

    reference = models.CharField(max_length=20, unique=True, editable=False)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='lost_found_reports',
    )
    report_type = models.CharField(max_length=5, choices=ReportType.choices)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=150)
    student_id = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=25, blank=True)
    category = models.CharField(max_length=70)
    item_name = models.CharField(max_length=120)
    description = models.TextField(max_length=1500)
    estimated_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    incident_date = models.DateField()
    incident_time = models.TimeField(null=True, blank=True)
    campus_location = models.CharField(max_length=120)
    location_details = models.TextField(max_length=1000, blank=True)
    liability_accepted = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REPORTED,
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        if self.incident_date and self.incident_date > timezone.localdate():
            raise ValidationError({'incident_date': 'Incident date cannot be in the future.'})
        if not self.liability_accepted:
            raise ValidationError({'liability_accepted': 'The liability notice must be accepted.'})

    def save(self, *args, **kwargs):
        if not self.reference:
            from django.db.models import Max
            current_max = Report.objects.aggregate(value=Max('pk'))['value'] or 0
            self.reference = f'LF-{timezone.now().year}-{current_max + 1:06d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.reference}: {self.item_name}'


class ReportAttachment(models.Model):
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file = models.FileField(upload_to='lost-found/reports/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.report.reference} attachment'


class Match(models.Model):
    lost_report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='lost_matches',
    )
    found_report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='found_matches',
    )
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    explanation = models.TextField(blank=True)
    is_approved = models.BooleanField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_matches',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['lost_report', 'found_report'],
                name='unique_lost_found_match',
            )
        ]

    def clean(self):
        if self.lost_report_id == self.found_report_id:
            raise ValidationError('A report cannot match itself.')
        if self.lost_report.report_type != Report.ReportType.LOST:
            raise ValidationError({'lost_report': 'Lost report must have lost type.'})
        if self.found_report.report_type != Report.ReportType.FOUND:
            raise ValidationError({'found_report': 'Found report must have found type.'})

    def __str__(self):
        return f'{self.lost_report.reference} / {self.found_report.reference}'


class Claim(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='claims',
    )
    claimant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='lost_found_claims',
    )
    match = models.ForeignKey(
        Match,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='claims',
    )
    verification_answers = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_claims',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    staff_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['report', 'claimant'],
                name='unique_report_claim',
            )
        ]

    def __str__(self):
        return f'{self.claimant.username}: {self.report.reference}'
