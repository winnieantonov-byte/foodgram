from rest_framework import permissions
from rest_framework.request import Request


class IsAuthorOrReadOnly(permissions.BasePermission):
    """Разрешает изменение контента только его автору."""

    def has_permission(self, request: Request, view) -> bool:
        return (
            request.method in permissions.SAFE_METHODS
            or request.user.is_authenticated
        )

    def has_object_permission(self, request: Request, view, obj) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user
