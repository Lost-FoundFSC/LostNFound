from rest_framework.permissions import BasePermission

CAMPUS_SECURITY_GROUP = 'Campus Security'


def is_campus_security(user):
    if not (user and user.is_authenticated):
        return False
    return user.is_superuser or user.groups.filter(name=CAMPUS_SECURITY_GROUP).exists()


class IsCampusSecurity(BasePermission):
    """Allows access only to Campus Security accounts (and superusers)."""

    message = 'Only Campus Security can view reports.'

    def has_permission(self, request, view):
        return is_campus_security(request.user)
