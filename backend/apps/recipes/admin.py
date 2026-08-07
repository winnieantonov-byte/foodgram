from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest

from apps.recipes.models import Favorite, Ingredient, Recipe, RecipeIngredient, ShoppingCart, Tag


class RecipeIngredientInline(admin.TabularInline):
    """Инлайн-интерфейс для удобного управления ингредиентами прямо внутри рецепта."""

    model = RecipeIngredient
    min_num = 1
    extra = 1


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    """Настройка панели администратора для рецептов."""

    # Выводим название, автора и кастомное вычисляемое поле количества в избранном
    list_display = ('id', 'name', 'author', 'get_favorites_count', 'pub_date')
    # Требование ТЗ: поиск по названию и по автору
    search_fields = ('name', 'author__username', 'author__email')
    # Требование ТЗ: фильтрация по тегам
    list_filter = ('tags',)
    inlines = (RecipeIngredientInline,)
    ordering = ('-pub_date',)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Оптимизация: аннотируем queryset количеством добавлений в избранное одним запросом."""
        queryset = super().get_queryset(request)
        return queryset.annotate(favorites_count_annotated=Count('favorites'))

    @admin.display(description='Добавлений в избранное')
    def get_favorites_count(self, obj: Recipe) -> int:
        """Отображает общее число добавлений рецепта в избранное."""
        return obj.favorites_count_annotated


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    """Настройка панели администратора для ингредиентов."""

    list_display = ('id', 'name', 'measurement_unit')
    # Требование ТЗ: для модели ингредиентов работает поиск по названию
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Настройка панели администратора для тегов."""

    list_display = ('id', 'name', 'color', 'slug')
    search_fields = ('name', 'slug')


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'recipe')


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'recipe')
