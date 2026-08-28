from django_filters import rest_framework as filters

from apps.recipes.models import Ingredient, Recipe, Tag


class IngredientFilter(filters.FilterSet):
    """Фильтр для ингредиентов по названию."""

    name = filters.CharFilter(lookup_expr='istartswith')

    class Meta:
        model = Ingredient
        fields = ('name',)


class RecipeFilter(filters.FilterSet):
    """Фильтр для рецептов по автору, избранному и корзине."""

    is_favorited = filters.NumberFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.NumberFilter(
        method='filter_is_in_shopping_cart'
    )
    tags = filters.ModelMultipleChoiceFilter(
        field_name='tags__slug',
        to_field_name='slug',
        queryset=Tag.objects.all(),
    )
    author = filters.NumberFilter(field_name='author__id')

    class Meta:
        model = Recipe
        fields = ('author', 'is_favorited', 'is_in_shopping_cart', 'tags')

    def _filter_relation(self, queryset, value, related_name):
        """Фильтрует рецепты по связи с пользователем."""
        user = getattr(self.request, 'user', None)
        if value and user and user.is_authenticated:
            is_true = value in (1, '1', True, 'true')
            if is_true:
                return queryset.filter(**{f'{related_name}__user': user})
        return queryset

    def filter_is_favorited(self, queryset, name, value):
        """Фильтрует рецепты, добавленные в избранное."""
        return self._filter_relation(queryset, value, 'favorite')

    def filter_is_in_shopping_cart(self, queryset, name, value):
        """Фильтрует рецепты, добавленные в корзину."""
        return self._filter_relation(queryset, value, 'shopping_cart')
