from django.urls import path, register_converter

from . import views
from .models import normalize_form_id


class FormIdConverter:
    """Matches form IDs in URLs.

    '#' cannot appear in a URL, so links use the ID without it
    (L384834901). L%23384834901 and lowercase also work.
    """

    regex = r'[LFlf]#?\d{9}'

    def to_python(self, value):
        return normalize_form_id(value)

    def to_url(self, value):
        return normalize_form_id(value).replace('#', '')


register_converter(FormIdConverter, 'form_id')

urlpatterns = [
    # Students
    path('', views.submit_report, name='report-submit'),
    path('mine/', views.my_reports, name='my-reports'),
    path('progress/<form_id:form_id>/', views.ReportProgress.as_view(), name='report-progress'),
    path('<form_id:form_id>/matches/', views.PotentialMatches.as_view(), name='potential-matches'),
    # Campus Security
    path('lost/', views.LostReportList.as_view(), name='lost-report-list'),
    path('found/', views.FoundReportList.as_view(), name='found-report-list'),
    path('archive/', views.ArchivedReportList.as_view(), name='archived-report-list'),
    path('<form_id:form_id>/', views.ReportDetail.as_view(), name='report-detail'),
    path('<form_id:form_id>/images/<int:image_id>/', views.report_image, name='report-image'),
]
