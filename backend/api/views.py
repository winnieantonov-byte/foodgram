from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet as DjoserUserViewSet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.request import Request
from rest_framework.response import Response

from api.filters import IngredientFilter, RecipeFilter
from api.permissions import IsAuthorOrReadOnly
from api.serializers import (
    AvatarSerializer,
    CompactRecipeSerializer,
    IngredientSerializer,
    RecipeReadSerializer,
    RecipeWriteSerializer,
    SubscriptionSerializer,
    TagSerializer,
)
from apps.recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
)
from apps.users.models import Subscription

User = get_user_model()


class UserViewSet(DjoserUserViewSet):
    """Вьюсет пользователей с подписками и управлением аватаром."""

    lookup_value_regex = r'\d+'

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
    )
    def me(self, request, *args, **kwargs):
        """Обработка эндпоинта /me."""
        return super().me(request, *args, **kwargs)

    @action(
        detail=False,
        methods=["put", "delete"],
        url_path="me/avatar",
        permission_classes=[IsAuthenticated],
    )
    def avatar(self, request: Request) -> Response:
        """Загрузка или удаление аватара пользователя."""
        user = request.user

        if request.method == "PUT":
            return self._update_avatar(user, request)
        return self._delete_avatar(user)

    def _update_avatar(self, user, request: Request) -> Response:
        """Обработка загрузки аватара."""
        serializer = AvatarSerializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _delete_avatar(self, user) -> Response:
        """Обработка удаления аватара."""
        if not user.avatar:
            return Response(
                {"errors": "Аватар уже удален или не существует."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.avatar.delete(save=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, permission_classes=[IsAuthenticated])
    def subscriptions(self, request: Request) -> Response:
        """Получение списка авторов, на которых подписан пользователь."""
        queryset = User.objects.filter(following__user=request.user)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = SubscriptionSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = SubscriptionSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
    )
    def subscribe(self, request, id=None):
        """Подписка или отписка от автора."""
        author = get_object_or_404(User, pk=id)
        user = request.user

        if user == author:
            return Response(
                {"errors": "Вы не можете подписаться на самого себя."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.method == "POST":
            return self._create_subscription(user, author, request)

        return self._delete_subscription(user, author)

    def _create_subscription(self, user, author, request: Request) -> Response:
        """Обработка создания подписки."""
        try:
            _, created = Subscription.objects.get_or_create(
                user=user, author=author
            )
        except IntegrityError:
            return Response(
                {"errors": "Вы уже подписаны на этого автора."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not created:
            return Response(
                {"errors": "Вы уже подписаны на этого автора."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SubscriptionSerializer(
            author, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _delete_subscription(self, user, author) -> Response:
        """Обработка удаления подписки."""
        deleted, _ = Subscription.objects.filter(
            user=user, author=author
        ).delete()

        if not deleted:
            return Response(
                {"errors": "Вы не подписаны на этого автора."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет для просмотра тегов без пагинации."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    pagination_class = None


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет для просмотра ингредиентов без пагинации."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [AllowAny]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
    pagination_class = None


class RecipeViewSet(viewsets.ModelViewSet):
    """Вьюсет для CRUD операций с рецептами."""

    queryset = Recipe.objects.all()
    lookup_value_regex = r'\d+'
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        """Возвращает соответствующий сериализатор для действия."""
        if self.action in ("list", "retrieve"):
            return RecipeReadSerializer
        return RecipeWriteSerializer

    def _manage_relation(self, request: Request, model, pk: int) -> Response:
        """Общий обработчик для избранного и корзины покупок."""
        recipe = get_object_or_404(Recipe, id=pk)
        user = request.user

        if request.method == "POST":
            return self._add_relation(model, user, recipe, request)

        return self._remove_relation(model, user, recipe)

    def _add_relation(self, model, user, recipe, request: Request) -> Response:
        """Добавляет рецепт в избранное или корзину пользователя."""
        _, created = model.objects.get_or_create(user=user, recipe=recipe)

        if not created:
            return Response(
                {"errors": "Рецепт уже добавлен в этот список."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CompactRecipeSerializer(
            recipe, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _remove_relation(self, model, user, recipe) -> Response:
        """Удаляет рецепт из избранного или корзины пользователя."""
        deleted, _ = model.objects.filter(user=user, recipe=recipe).delete()

        if not deleted:
            return Response(
                {"errors": "Рецепт нет в этом списке."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
    )
    def favorite(self, request: Request, pk: int = None) -> Response:
        """Добавляет или удаляет рецепт из избранного."""
        return self._manage_relation(request, Favorite, pk)

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
    )
    def shopping_cart(self, request: Request, pk: int = None) -> Response:
        """Добавляет или удаляет рецепт из корзины покупок."""
        return self._manage_relation(request, ShoppingCart, pk)

    @action(
        detail=True,
        methods=["get"],
        url_path="get-link",
        permission_classes=[AllowAny],
    )
    def get_link(self, request: Request, pk: int) -> Response:
        """Генерирует короткую ссылку на рецепт."""
        recipe = get_object_or_404(Recipe, id=pk)
        short_link = request.build_absolute_uri(f"/s/{recipe.id}")
        return Response({"short-link": short_link}, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
    )
    def download_shopping_cart(self, request: Request) -> HttpResponse:
        """Скачивает список покупок в виде текстового файла."""
        user = request.user

        if not ShoppingCart.objects.filter(user=user).exists():
            return Response(
                {"errors": "Ваш список покупок пока пуст."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ingredients = (
            RecipeIngredient.objects.filter(recipe__shopping_cart__user=user)
            .values("ingredient__name", "ingredient__measurement_unit")
            .annotate(total_amount=Sum("amount"))
            .order_by("ingredient__name")
        )

        file_content = self._build_shopping_cart_content(user, ingredients)

        response = HttpResponse(
            file_content, content_type="text/plain; charset=utf-8"
        )
        response["Content-Disposition"] = (
            'attachment; filename="shopping_cart.txt"'
        )
        return response

    def _build_shopping_cart_content(self, user, ingredients) -> str:
        """Формирует содержимое файла со списком покупок."""
        lines = [
            "Список покупок Foodgram\n",
            f"Для: {user.get_full_name() or user.username}\n\n",
        ]

        for ing in ingredients:
            name = ing["ingredient__name"]
            amount = ing["total_amount"]
            unit = ing["ingredient__measurement_unit"]
            lines.append(f"• {name} — {amount} {unit}\n")

        return "".join(lines)
