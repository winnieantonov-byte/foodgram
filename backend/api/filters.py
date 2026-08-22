import django_filters
from django.contrib.auth import get_user_model
from django_filters import BaseInFilter

from apps.recipes.models import Ingredient, Recipe

User = get_user_model()


class IngredientFilter(django_filters.FilterSet):
    """Фильтр для ингредиентов по названию."""

    name = django_filters.CharFilter(lookup_expr='istartswith')

    class Meta:
        model = Ingredient
        fields = ('name',)


class RecipeFilter(django_filters.FilterSet):
    """Фильтр для рецептов по автору, избранному и корзине."""

    author = django_filters.ModelChoiceFilter(queryset=User.objects.all())
    is_favorited = django_filters.NumberFilter(method='filter_is_favorited')
    is_in_shopping_cart = django_filters.NumberFilter(method='filter_is_in_shopping_cart')
    tags = BaseInFilter(method='filter_tags')

    class Meta:
        model = Recipe
        fields = ('author', 'is_favorited', 'is_in_shopping_cart', 'tags')

    def _filter_relation(self, queryset, value, related_name):
        """Фильтрует рецепты по связи с пользователем."""
        user = self.request.user
        if bool(value) and user.is_authenticated:
            return queryset.filter(**{f'{related_name}__user': user})
        return queryset

    def filter_is_favorited(self, queryset, name, value):
        """Фильтрует рецепты, добавленные в избранное."""
        return self._filter_relation(queryset, value, 'favorite')

    def filter_is_in_shopping_cart(self, queryset, name, value):
        """Фильтрует рецепты, добавленные в корзину."""
        return self._filter_relation(queryset, value, 'shopping_cart')

    def filter_tags(self, queryset, name, value):
        """
        Фильтрует рецепты по тегам (AND-условие).
        Рецепт должен содержать все указанные теги.
        """
        if not value:
            return queryset

        for tag_slug in value:
            queryset = queryset.filter(tags__slug=tag_slug)

        return queryset
