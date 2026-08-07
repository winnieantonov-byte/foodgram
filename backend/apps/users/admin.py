from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.users.models import User, Subscription


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Настройка панели администратора для кастомной модели пользователя."""

    # Поля, отображаемые в списке пользователей
    list_display = ('id', 'username', 'email', 'first_name', 'last_name', 'is_staff')
    # Требование ТЗ: доступен поиск по имени и адресу электронной почты
    search_fields = ('username', 'email')
    list_filter = ('is_staff', 'is_active')
    ordering = ('id',)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Настройка панели администратора для модели подписок."""

    list_display = ('id', 'user', 'author')
    search_fields = ('user__username', 'author__username', 'user__email', 'author__email')
