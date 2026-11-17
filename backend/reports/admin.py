from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from .archive import change_status
from .models import (
    ArchivedReport, ArchivedReportImage, FoundReport, FoundReportImage,
    LostReport, LostReportImage, ReportStatus,
)


# ------------------------------------------------------------------ photos

class ReportImageInline(admin.TabularInline):
    extra = 0
    fields = ('preview', 'uploaded_at')
    readonly_fields = ('preview', 'uploaded_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='Photo')
    def preview(self, image):
        url = reverse('report-image', args=[image.report.form_id, image.pk])
        return format_html('<a href="{0}" target="_blank"><img src="{0}" style="max-height:160px"></a>', url)


class LostReportImageInline(ReportImageInline):
    model = LostReportImage


class FoundReportImageInline(ReportImageInline):
    model = FoundReportImage


class ArchivedReportImageInline(ReportImageInline):
    model = ArchivedReportImage


# ----------------------------------------------------------------- actions

def status_action(new_status, description):
    def action(modeladmin, request, queryset):
        count = 0
        for report in queryset:
            change_status(report, new_status)
            count += 1
        modeladmin.message_user(request, f'{count} report(s) set to {new_status.label}.', messages.SUCCESS)

    action.__name__ = f'set_{new_status.value}'
    return admin.action(description=description)(action)


OPEN_ACTIONS = [
    status_action(ReportStatus.POSSIBLE_MATCH, 'Set status: Possible match'),
    status_action(ReportStatus.UNDER_VERIFICATION, 'Set status: Under verification'),
    status_action(ReportStatus.READY_FOR_PICKUP, 'Set status: Ready for pickup'),
    status_action(ReportStatus.RETURNED, 'Returned (moves to archive)'),
    status_action(ReportStatus.CLOSED, 'Closed (moves to archive)'),
]
ARCHIVE_ACTIONS = [
    status_action(ReportStatus.REPORTED, 'Reopen (moves back to open reports)'),
]


# ------------------------------------------------------------------ admins

class ReportAdmin(admin.ModelAdmin):
    list_display = ('form_id', 'item_name', 'category', 'campus_location',
                    'incident_date', 'student_id', 'status', 'created_at')
    list_filter = ('status', 'category', 'campus_location')
    search_fields = ('form_id', 'item_name', 'description', 'location_details',
                     'full_name', 'email', 'student_id')
    readonly_fields = ('form_id', 'status', 'created_at', 'updated_at')
    actions = OPEN_ACTIONS


@admin.register(LostReport)
class LostReportAdmin(ReportAdmin):
    inlines = [LostReportImageInline]


@admin.register(FoundReport)
class FoundReportAdmin(ReportAdmin):
    inlines = [FoundReportImageInline]


@admin.register(ArchivedReport)
class ArchivedReportAdmin(ReportAdmin):
    list_display = ('form_id', 'report_type', 'item_name', 'status',
                    'archive_semester', 'completed_at')
    list_filter = ('report_type', 'status', 'archive_semester', 'category')
    readonly_fields = ('form_id', 'report_type', 'status', 'completed_at',
                       'archive_semester', 'created_at', 'updated_at')
    inlines = [ArchivedReportImageInline]
    actions = ARCHIVE_ACTIONS
