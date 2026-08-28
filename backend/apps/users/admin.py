from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from apps.users.models import Subscription

User = get_user_model()


@admin.register(User)
class UserAdminConfig(UserAdmin):
    """Настройка отображения пользователей в админке."""

    list_display = (
        'id', 'username', 'email', 'first_name', 'last_name', 'is_staff'
    )
    search_fields = ('username', 'email')
    list_filter = ('is_staff', 'is_active')
    ordering = ('username',)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Настройка отображения подписок в админке."""

    list_display = ('id', 'user', 'author')
    search_fields = (
        'user__username',
        'author__username',
        'user__email',
        'author__email',
    )
