from django import forms
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from .archive import MatchError, change_status, check_match, match_reports, unmatch_report
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
        partners = []
        for report in queryset:
            if report.matched_form_id:
                partners.append(report.matched_form_id)
            change_status(report, new_status)
            count += 1
        message = f'{count} report(s) set to {new_status.label}.'
        if partners and new_status in (ReportStatus.RETURNED, ReportStatus.REPORTED):
            message += f' Matched report(s) updated too: {", ".join(partners)}.'
        modeladmin.message_user(request, message, messages.SUCCESS)

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

class ReportAdminForm(forms.ModelForm):
    """Checks the Matched form ID box before saving."""

    def clean_matched_form_id(self):
        value = (self.cleaned_data.get('matched_form_id') or '').strip().upper()
        if not value or value == (self.instance.matched_form_id or ''):
            return value
        if not self.instance.pk:
            raise forms.ValidationError('Save the report first, then add the match.')
        try:
            other = check_match(self.instance, value)
        except MatchError as error:
            raise forms.ValidationError(str(error))
        return other.form_id


class ReportAdmin(admin.ModelAdmin):
    form = ReportAdminForm
    list_display = ('form_id', 'item_name', 'category', 'campus_location',
                    'incident_date', 'student_id', 'status', 'matched_form_id', 'created_at')
    list_filter = ('status', 'category', 'campus_location')
    search_fields = ('form_id', 'matched_form_id', 'item_name', 'description',
                     'location_details', 'full_name', 'email', 'student_id')
    readonly_fields = ('form_id', 'status', 'created_at', 'updated_at')
    actions = OPEN_ACTIONS

    def get_fields(self, request, obj=None):
        # Show the form ID and the match box at the top of the page.
        first = ['form_id', 'matched_form_id']
        return first + [f for f in super().get_fields(request, obj) if f not in first]

    def save_model(self, request, obj, form, change):
        new_match = form.cleaned_data.get('matched_form_id', '')
        if change and 'matched_form_id' in form.changed_data:
            obj.matched_form_id = form.initial.get('matched_form_id', '')
            super().save_model(request, obj, form, change)
            if new_match:
                match_reports(obj, new_match)
                self.message_user(request, f'{obj.form_id} and {new_match} are now matched.', messages.SUCCESS)
            else:
                unmatch_report(obj)
                self.message_user(request, f'Match removed from {obj.form_id}.', messages.SUCCESS)
            return
        super().save_model(request, obj, form, change)


@admin.register(LostReport)
class LostReportAdmin(ReportAdmin):
    inlines = [LostReportImageInline]


@admin.register(FoundReport)
class FoundReportAdmin(ReportAdmin):
    inlines = [FoundReportImageInline]


@admin.register(ArchivedReport)
class ArchivedReportAdmin(ReportAdmin):
    list_display = ('form_id', 'report_type', 'item_name', 'status',
                    'matched_form_id', 'archive_semester', 'completed_at')
    list_filter = ('report_type', 'status', 'archive_semester', 'category')
    readonly_fields = ('form_id', 'report_type', 'status', 'completed_at',
                       'archive_semester', 'created_at', 'updated_at')
    inlines = [ArchivedReportImageInline]
    actions = ARCHIVE_ACTIONS
