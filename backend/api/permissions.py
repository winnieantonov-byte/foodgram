from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Разрешает чтение всем пользователям.
    Изменение и удаление разрешено только автору объекта.
    """

    def has_permission(self, request, view):
        """Проверяет право на выполнение действия."""
        if view.action == 'create':
            return request.user.is_authenticated
        return True

    def has_object_permission(self, request, view, obj):
        """Проверяет право на выполнение действия с объектом."""
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user
