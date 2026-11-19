from django.db import transaction
from django.http import FileResponse, Http404
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .archive import (
    MatchError, change_status, find_report, match_reports, reports_for_email,
    unmatch_report,
)
from .images import MAX_IMAGES_PER_REPORT, ImageUploadError, clean_image
from .models import (
    OPEN_STATUSES, ArchivedReport, FoundReport, FoundReportImage, LostReport,
    LostReportImage, ReportType,
)
from .permissions import IsCampusSecurity
from .serializers import (
    ArchivedReportSerializer, FoundReportSerializer, LostReportSerializer,
    ProgressSerializer, StatusUpdateSerializer, full_report_data,
)

SERIALIZERS = {ReportType.LOST: LostReportSerializer, ReportType.FOUND: FoundReportSerializer}
IMAGE_MODELS = {ReportType.LOST: LostReportImage, ReportType.FOUND: FoundReportImage}


# ---------------------------------------------------------------- students

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def submit_report(request):
    """Single endpoint the report form posts to.

    Uses `reportType` ('lost' or 'found') to save into the matching table.
    Accepts JSON, or multipart/form-data with up to 5 photos under `images`.
    Returns the new form ID (L#... or F#...).
    """
    report_type = request.data.get('reportType')
    serializer_class = SERIALIZERS.get(report_type)
    if serializer_class is None:
        return Response(
            {'reportType': ["Must be 'lost' or 'found'."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Check every photo before saving anything, so a bad photo
    # never leaves behind a half-saved report.
    uploads = request.FILES.getlist('images')
    if len(uploads) > MAX_IMAGES_PER_REPORT:
        return Response(
            {'images': [f'You can upload up to {MAX_IMAGES_PER_REPORT} photos.']},
            status=status.HTTP_400_BAD_REQUEST,
        )
    cleaned, errors = [], []
    for upload in uploads:
        try:
            cleaned.append(clean_image(upload))
        except ImageUploadError as error:
            errors.append(str(error))
    if errors:
        return Response({'images': errors}, status=status.HTTP_400_BAD_REQUEST)

    image_model = IMAGE_MODELS[report_type]
    with transaction.atomic():
        report = serializer.save()
        for photo in cleaned:
            image_model.objects.create(report=report, image=photo)

    return Response(
        {'formId': report.form_id, 'reportType': report_type,
         'status': report.status, 'imageCount': len(cleaned)},
        status=status.HTTP_201_CREATED,
    )


class ReportProgress(APIView):
    """Anyone with a form ID can check its progress (no personal details).

    Rate limited so form IDs cannot be guessed by trying many in a row.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'report-progress'

    def get(self, request, form_id):
        report = find_report(form_id)
        if report is None:
            raise Http404
        return Response(ProgressSerializer(report).data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def my_reports(request):
    """Student dashboard: every report submitted with the signed-in user's email."""
    if not request.user.email:
        return Response([])
    reports = reports_for_email(request.user.email)
    return Response(ProgressSerializer(reports, many=True).data)


# --------------------------------------------------------- Campus Security

def _status_filter(request):
    wanted = request.query_params.get('status')
    if wanted and wanted not in OPEN_STATUSES:
        raise ValidationError({'status': [f'Must be one of: {", ".join(OPEN_STATUSES)}.']})
    return wanted


class OpenReportList(generics.ListAPIView):
    """Open lost or found reports. Optional filter: ?status=possible_match"""

    permission_classes = [IsCampusSecurity]

    def get_queryset(self):
        queryset = self.model.objects.prefetch_related('images')
        wanted = _status_filter(self.request)
        return queryset.filter(status=wanted) if wanted else queryset


class LostReportList(OpenReportList):
    model = LostReport
    serializer_class = LostReportSerializer


class FoundReportList(OpenReportList):
    model = FoundReport
    serializer_class = FoundReportSerializer


class ArchivedReportList(generics.ListAPIView):
    """Archived reports. Optional filters: ?type=lost|found  ?semester=Fall 2026"""

    permission_classes = [IsCampusSecurity]
    serializer_class = ArchivedReportSerializer

    def get_queryset(self):
        queryset = ArchivedReport.objects.prefetch_related('images')
        report_type = self.request.query_params.get('type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        semester = self.request.query_params.get('semester')
        if semester:
            queryset = queryset.filter(archive_semester=semester)
        return queryset


class ReportDetail(APIView):
    """One report by form ID, open or archived.

    GET   -> full report
    PATCH -> {"status": "<new status>"}. Returned/closed/cancelled moves the
             report to the archive; an open status moves it back.
             {"matchedFormId": "F#123456789"} links a lost report and a found
             report to each other ("" removes the link). When matched reports
             are marked returned, both move to the archive together.
             Both keys can be sent at once; the match is saved first.
    """

    permission_classes = [IsCampusSecurity]

    def get_report(self, form_id):
        report = find_report(form_id)
        if report is None:
            raise Http404
        return report

    def get(self, request, form_id):
        return Response(full_report_data(self.get_report(form_id), request))

    def patch(self, request, form_id):
        report = self.get_report(form_id)
        serializer = StatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            if 'matchedFormId' in data:
                try:
                    if data['matchedFormId'].strip():
                        match_reports(report, data['matchedFormId'])
                    else:
                        unmatch_report(report)
                except MatchError as error:
                    return Response({'matchedFormId': [str(error)]}, status=status.HTTP_400_BAD_REQUEST)
                report = find_report(report.form_id)
            if 'status' in data:
                report = change_status(report, data['status'])

        report = find_report(report.form_id)  # reload with photos
        return Response(full_report_data(report, request))


@api_view(['GET'])
@permission_classes([IsCampusSecurity])
def report_image(request, form_id, image_id):
    """Campus Security only: return one photo attached to a report."""
    report = find_report(form_id)
    if report is None:
        raise Http404
    image = report.images.filter(pk=image_id).first()
    if image is None:
        raise Http404
    return FileResponse(image.image.open('rb'))
