from django.contrib import admin
from django.utils import timezone

from .models import Claim, Match, Profile, Report, ReportAttachment


class ReportAttachmentInline(admin.TabularInline):
    model = ReportAttachment
    extra = 0


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        'reference', 'item_name', 'report_type', 'category',
        'status', 'campus_location', 'incident_date', 'created_at',
    )
    list_filter = ('report_type', 'status', 'category', 'campus_location')
    search_fields = ('reference', 'item_name', 'description', 'email', 'submitted_by__username')
    readonly_fields = ('reference', 'submitted_by', 'created_at', 'updated_at')
    inlines = (ReportAttachmentInline,)
    actions = ('mark_ready_for_pickup', 'mark_returned', 'close_reports')

    @admin.action(description='Mark selected reports ready for pickup')
    def mark_ready_for_pickup(self, request, queryset):
        queryset.update(status=Report.Status.READY_FOR_PICKUP)

    @admin.action(description='Mark selected reports returned')
    def mark_returned(self, request, queryset):
        queryset.update(status=Report.Status.RETURNED)

    @admin.action(description='Close selected reports')
    def close_reports(self, request, queryset):
        queryset.update(status=Report.Status.CLOSED)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        'lost_report', 'found_report', 'score', 'is_approved',
        'reviewed_by', 'reviewed_at',
    )
    list_filter = ('is_approved',)
    actions = ('approve_matches', 'reject_matches')

    @admin.action(description='Approve selected matches')
    def approve_matches(self, request, queryset):
        queryset.update(
            is_approved=True,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        for match in queryset:
            match.lost_report.status = Report.Status.POSSIBLE_MATCH
            match.lost_report.save(update_fields=['status', 'updated_at'])

    @admin.action(description='Reject selected matches')
    def reject_matches(self, request, queryset):
        queryset.update(
            is_approved=False,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = (
        'report', 'claimant', 'status', 'reviewed_by',
        'reviewed_at', 'created_at',
    )
    list_filter = ('status',)
    search_fields = ('report__reference', 'claimant__username', 'staff_notes')
    readonly_fields = ('created_at', 'updated_at')
    actions = ('approve_claims', 'reject_claims')

    @admin.action(description='Approve selected claims')
    def approve_claims(self, request, queryset):
        queryset.update(
            status=Claim.Status.APPROVED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

    @admin.action(description='Reject selected claims')
    def reject_claims(self, request, queryset):
        queryset.update(
            status=Claim.Status.REJECTED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'user', 'role', 'ram_id', 'student_id')
    list_filter = ('role',)
    search_fields = ('full_name', 'ram_id', 'student_id', 'user__username', 'user__email')
