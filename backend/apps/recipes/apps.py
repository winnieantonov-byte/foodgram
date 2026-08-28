from django.apps import AppConfig


class RecipesConfig(AppConfig):
    """Конфигурация приложения рецептов."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.recipes'
    verbose_name = 'Контент рецептов'
