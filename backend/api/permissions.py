from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Разрешает чтение всем пользователям.
    Изменение и удаление разрешено только автору объекта.
    """

    def has_object_permission(self, request, view, obj):
        """Проверяет право на выполнение действия с объектом."""
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user
