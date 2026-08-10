from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from api.filters import IngredientFilter, RecipeFilter
from api.permissions import IsAuthorOrReadOnly
from api.serializers import (
    CompactRecipeSerializer,
    IngredientSerializer,
    RecipeReadSerializer,
    RecipeWriteSerializer,
    SubscriptionSerializer,
    TagSerializer,
)
from apps.recipes.models import (
    Favorite, Ingredient, Recipe, RecipeIngredient, ShoppingCart, Tag
)
from apps.users.models import Subscription

User = get_user_model()


# =====================================================================
# ВЬЮСЕТ ПОЛЬЗОВАТЕЛЕЙ И ПОДПИСОК (USERS & SUBSCRIPTIONS)
# =====================================================================

class CustomUserViewSet(UserViewSet):
    """Кастомный вьюсет пользователей, расширяющий Djoser подписками."""

    @action(
        detail=False,
        permission_classes=[IsAuthenticated],
        serializer_class=SubscriptionSerializer
    )
    def subscriptions(self, request: Request) -> Response:
        """Получить список авторов, на которых подписан пользователь."""
        queryset = User.objects.filter(following__user=request.user)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(
                page, many=True, context={'request': request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(
            queryset, many=True, context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def subscribe(self, request: Request, id: int = None) -> Response:
        """Подписаться или отписаться от конкретного автора."""
        author = get_object_or_404(User, id=id)
        user = request.user

        if request.method == 'POST':
            if user == author:
                return Response(
                    {'errors': 'Вы не можете подписаться на самого себя.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if Subscription.objects.filter(user=user, author=author).exists():
                return Response(
                    {'errors': 'Вы уже подписаны на этого автора.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            Subscription.objects.create(user=user, author=author)
            serializer = SubscriptionSerializer(
                author, context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            subscription = Subscription.objects.filter(
                user=user, author=author
            )
            if not subscription.exists():
                return Response(
                    {'errors': 'Вы не подписаны на этого автора.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================================
# ВЬЮСЕТЫ СУЩНОСТЕЙ РЕЦЕПТОВ (TAGS, INGREDIENTS, RECIPES)
# =====================================================================

class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет для просмотра тегов (только чтение для всех)."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    pagination_class = None


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет для просмотра ингредиентов с фильтрацией."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [AllowAny]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
    pagination_class = None


class RecipeViewSet(viewsets.ModelViewSet):
    """Центральный вьюсет рецептов (CRUD, Избранное, Корзина)."""

    queryset = Recipe.objects.all()
    permission_classes = [IsAuthorOrReadOnly]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return RecipeReadSerializer
        return RecipeWriteSerializer

    def _manage_relation(
        self, request: Request, model, pk: int = None
    ) -> Response:
        """Внутренний DRY-метод для связи рецептов со списками."""
        recipe = get_object_or_404(Recipe, id=pk)
        user = request.user

        if request.method == 'POST':
            if model.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {'errors': 'Рецепт уже добавлен в этот список.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            model.objects.create(user=user, recipe=recipe)
            serializer = CompactRecipeSerializer(
                recipe, context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            relation = model.objects.filter(user=user, recipe=recipe)
            if not relation.exists():
                return Response(
                    {'errors': 'Рецепта нет в этом списке.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            relation.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def favorite(self, request: Request, pk: int = None) -> Response:
        """Добавить или удалить рецепт из Избранного."""
        return self._manage_relation(request, Favorite, pk)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def shopping_cart(self, request: Request, pk: int = None) -> Response:
        """Добавить или удалить рецепт из Списка покупок."""
        return self._manage_relation(request, ShoppingCart, pk)

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated]
    )
    def download_shopping_cart(self, request: Request) -> HttpResponse:
        """Агрегационный сервис: подсчет ингредиентов и отгрузка TXT."""
        user = request.user
        if not user.shopping_cart.exists():
            return Response(
                {'errors': 'Ваш список покупок пока пуст.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        ingredients = (
            RecipeIngredient.objects.filter(recipe__shopping_cart__user=user)
            .values('ingredient__name', 'ingredient__measurement_unit')
            .annotate(total_amount=Sum('amount'))
            .order_by('ingredient__name')
        )

        file_lines = [
            'Список покупок Foodgram\n',
            f'Для: {user.get_full_name() or user.username}\n\n'
        ]
        for ing in ingredients:
            name = ing['ingredient__name']
            unit = ing['ingredient__measurement_unit']
            amount = ing['total_amount']
            file_lines.append(f'• {name} — {amount} {unit}\n')

        file_content = ''.join(file_lines)

        response = HttpResponse(
            file_content, content_type='text/plain; charset=utf-8'
        )
        response['Content-Disposition'] = (
            'attachment; filename="shopping_cart.txt"'
        )
        return response
