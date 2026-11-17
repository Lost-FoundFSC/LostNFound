from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_campus_security_group(sender, using='default', **kwargs):
    """Create the Campus Security group with view/change rights on reports."""
    from django.contrib.auth.models import Group, Permission
    from django.db import connections

    # Skip if Django's user/permission tables have not been created yet
    # (for example when only this app is migrated on a new database).
    tables = connections[using].introspection.table_names()
    if 'auth_group' not in tables or 'auth_permission' not in tables:
        return

    from .permissions import CAMPUS_SECURITY_GROUP

    group, _ = Group.objects.get_or_create(name=CAMPUS_SECURITY_GROUP)
    perms = Permission.objects.filter(
        content_type__app_label='reports',
        codename__in=[
            'view_lostreport', 'change_lostreport',
            'view_foundreport', 'change_foundreport',
            'view_archivedreport', 'change_archivedreport',
            'view_lostreportimage', 'view_foundreportimage', 'view_archivedreportimage',
        ],
    )
    group.permissions.add(*perms)


class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reports'

    def ready(self):
        post_migrate.connect(create_campus_security_group, sender=self)
