import django_filters
from django.contrib.auth import get_user_model

from apps.recipes.models import Ingredient, Recipe, Tag

User = get_user_model()


class IngredientFilter(django_filters.FilterSet):
    """Фильтрация ингредиентов по названию (поиск по началу строки)."""

    name = django_filters.CharFilter(lookup_expr='istartswith')

    class Meta:
        model = Ingredient
        fields = ('name',)


class RecipeFilter(django_filters.FilterSet):
    """Комплексный фильтр для рецептов."""

    author = django_filters.ModelChoiceFilter(queryset=User.objects.all())
    tags = django_filters.ModelMultipleChoiceFilter(
        field_name='tags__slug',
        to_field_name='slug',
        queryset=Tag.objects.all()
    )
    is_favorited = django_filters.NumberFilter(method='filter_is_favorited')
    is_in_shopping_cart = django_filters.NumberFilter(method='filter_is_in_shopping_cart')

    class Meta:
        model = Recipe
        fields = ('author', 'tags', 'is_favorited', 'is_in_shopping_cart')

    def _filter_relation(self, queryset, value, related_name):
        user = self.request.user
        if value and user.is_authenticated:
            return queryset.filter(**{f'{related_name}__user': user})
        return queryset

    def filter_is_favorited(self, queryset, name, value):
        return self._filter_relation(queryset, value, 'favorites')

    def filter_is_in_shopping_cart(self, queryset, name, value):
        return self._filter_relation(queryset, value, 'shopping_cart')
