import re

from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers

from .models import ArchivedReport, FoundReport, LostReport, ReportStatus

# Same rule as frontend/src/auth/fscEmail.js: the letter R followed by 8 digits.
RAM_ID_PATTERN = re.compile(r'^R\d{8}$')

STATUS_LABELS = dict(ReportStatus.choices)


class ReportSerializer(serializers.ModelSerializer):
    """Full report. Accepts the camelCase payload from ReportPage.jsx and is
    what Campus Security sees."""

    formId = serializers.CharField(source='form_id', read_only=True)
    reportType = serializers.CharField(source='report_type', read_only=True)
    fullName = serializers.CharField(source='full_name', max_length=100)
    studentId = serializers.CharField(
        source='student_id', max_length=20, required=False, allow_blank=True,
    )
    phone = serializers.CharField(max_length=25)
    itemName = serializers.CharField(source='item_name', max_length=120)
    estimatedValue = serializers.DecimalField(
        source='estimated_value', max_digits=9, decimal_places=2,
        min_value=0, required=False, allow_null=True,
    )
    incidentDate = serializers.DateField(
        source='incident_date', required=False, allow_null=True,
    )
    incidentTime = serializers.TimeField(
        source='incident_time', required=False, allow_null=True,
    )
    campusLocation = serializers.CharField(
        source='campus_location', max_length=100, required=False, allow_blank=True,
    )
    locationDetails = serializers.CharField(
        source='location_details', max_length=1000, required=False, allow_blank=True,
    )
    # Map pin (future campus map feature). Optional; send both or neither.
    mapLatitude = serializers.DecimalField(
        source='map_latitude', max_digits=9, decimal_places=6,
        min_value=-90, max_value=90, required=False, allow_null=True,
        coerce_to_string=False,
    )
    mapLongitude = serializers.DecimalField(
        source='map_longitude', max_digits=9, decimal_places=6,
        min_value=-180, max_value=180, required=False, allow_null=True,
        coerce_to_string=False,
    )
    liabilityAccepted = serializers.BooleanField(source='liability_accepted')
    status = serializers.CharField(read_only=True)
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    completedAt = serializers.DateTimeField(source='completed_at', read_only=True)
    archiveSemester = serializers.CharField(source='archive_semester', read_only=True)
    matchedFormId = serializers.CharField(source='matched_form_id', read_only=True)
    images = serializers.SerializerMethodField()

    class Meta:
        fields = [
            'formId', 'reportType', 'fullName', 'email', 'studentId', 'phone',
            'category', 'itemName', 'description', 'estimatedValue',
            'incidentDate', 'incidentTime', 'campusLocation', 'locationDetails',
            'mapLatitude', 'mapLongitude', 'liabilityAccepted', 'status', 'isActive', 'createdAt',
            'completedAt', 'archiveSemester', 'matchedFormId', 'images',
        ]

    def to_internal_value(self, data):
        # Works for both JSON and multipart (form + photos) submissions.
        # Photos are handled separately in the view, so only text fields are kept.
        data = {key: data.get(key) for key in data if key != 'images'}
        # The HTML form sends '' for empty optional number/time inputs.
        for key in ('estimatedValue', 'incidentDate', 'incidentTime', 'mapLatitude', 'mapLongitude'):
            if data.get(key) == '':
                data[key] = None
        return super().to_internal_value(data)

    def get_images(self, report):
        request = self.context.get('request')
        images = []
        for image in report.images.all():
            url = reverse('report-image', args=[report.form_id, image.pk])
            images.append({
                'id': image.pk,
                'url': request.build_absolute_uri(url) if request else url,
                'uploadedAt': image.uploaded_at,
            })
        return images

    def validate(self, attrs):
        has_latitude = attrs.get('map_latitude') is not None
        has_longitude = attrs.get('map_longitude') is not None
        if has_latitude != has_longitude:
            raise serializers.ValidationError(
                {'mapLatitude': ['Send both mapLatitude and mapLongitude, or neither.']}
            )
        return attrs

    def validate_phone(self, value):
        digits = ''.join(ch for ch in value if ch.isdigit())
        if len(digits) == 11 and digits.startswith('1'):
            digits = digits[1:]
        if len(digits) != 10:
            raise serializers.ValidationError(
                'Enter a 10-digit phone number, like (516) 555-1234.'
            )
        return f'({digits[:3]}) {digits[3:6]}-{digits[6:]}'

    def validate_studentId(self, value):
        ram_id = value.strip().upper()
        if ram_id and not RAM_ID_PATTERN.match(ram_id):
            raise serializers.ValidationError(
                'A RAM ID is the letter R followed by 8 digits, like R01234567.'
            )
        return ram_id

    def validate_incidentDate(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError('Date cannot be in the future.')
        return value

    def validate_liabilityAccepted(self, value):
        if not value:
            raise serializers.ValidationError('You must acknowledge the liability notice.')
        return value


class LostReportSerializer(ReportSerializer):
    class Meta(ReportSerializer.Meta):
        model = LostReport


class FoundReportSerializer(ReportSerializer):
    class Meta(ReportSerializer.Meta):
        model = FoundReport


class ArchivedReportSerializer(ReportSerializer):
    class Meta(ReportSerializer.Meta):
        model = ArchivedReport


def full_report_data(report, request):
    """Serialize an open or archived report for Campus Security."""
    serializer_class = {
        LostReport: LostReportSerializer,
        FoundReport: FoundReportSerializer,
        ArchivedReport: ArchivedReportSerializer,
    }[type(report)]
    return serializer_class(report, context={'request': request}).data


class ProgressSerializer(serializers.Serializer):
    """What the person who submitted a report can see: progress only.

    No contact details, RAM ID, description, or photos.
    """

    formId = serializers.CharField(source='form_id')
    reportType = serializers.CharField(source='report_type')
    itemName = serializers.CharField(source='item_name')
    category = serializers.CharField()
    campusLocation = serializers.CharField(source='campus_location')
    incidentDate = serializers.DateField(source='incident_date', allow_null=True)
    status = serializers.CharField()
    statusLabel = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source='is_active')
    submittedAt = serializers.DateTimeField(source='created_at')
    updatedAt = serializers.DateTimeField(source='updated_at')
    completedAt = serializers.DateTimeField(source='completed_at')
    archiveSemester = serializers.CharField(source='archive_semester')

    def get_statusLabel(self, report):
        return STATUS_LABELS.get(report.status, report.status)


class StatusUpdateSerializer(serializers.Serializer):
    """Used by Campus Security to update a report.

    status:        move the report to another stage
    matchedFormId: link this report to its lost/found match ('' removes the match)
    At least one is required.
    """

    status = serializers.ChoiceField(choices=ReportStatus.choices, required=False)
    matchedFormId = serializers.CharField(required=False, allow_blank=True, max_length=20)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Send a status, a matchedFormId, or both.')
        return attrs
