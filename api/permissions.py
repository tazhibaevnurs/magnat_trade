from rest_framework import permissions


class IsIntegrationCaller(permissions.BasePermission):
    """Доступ только после успешной IntegrationAPIAuthentication."""

    def has_permission(self, request, view):
        return request.auth in ("integration-api-key", "integration-basic")
