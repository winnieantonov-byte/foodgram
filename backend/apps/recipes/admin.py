from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest

from apps.recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
)


class RecipeIngredientInline(admin.TabularInline):
    """Встроенная форма для управления ингредиентами в рецепте."""

    model = RecipeIngredient
    min_num = 1
    extra = 1


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    """Настройка отображения рецептов в админке."""

    list_display = ('id', 'name', 'author', 'get_favorites_count', 'pub_date')
    search_fields = ('name', 'author__username', 'author__email')
    list_filter = ('tags',)
    inlines = (RecipeIngredientInline,)
    ordering = ('-pub_date',)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Оптимизирует запрос, добавляя количество добавлений в избранное."""
        return super().get_queryset(request).annotate(
            favorites_count_annotated=Count('favorites'),
        )

    @admin.display(description='Добавлений в избранное')
    def get_favorites_count(self, obj: Recipe) -> int:
        """Возвращает общее количество добавлений рецепта в избранное."""
        return obj.favorites_count_annotated


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    """Настройка отображения ингредиентов в админке."""

    list_display = ('id', 'name', 'measurement_unit')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Настройка отображения тегов в админке."""

    list_display = ('id', 'name', 'slug')
    search_fields = ('name', 'slug')


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    """Настройка отображения избранного в админке."""

    list_display = ('id', 'user', 'recipe')


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    """Настройка отображения корзины в админке."""

    list_display = ('id', 'user', 'recipe')
