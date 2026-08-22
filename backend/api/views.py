import base64
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet
from rest_framework import serializers, status, viewsets
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
from apps.recipes.models import Favorite, Ingredient, Recipe
from apps.recipes.models import RecipeIngredient, ShoppingCart, Tag
from apps.users.models import Subscription

User = get_user_model()


class Base64ImageField(serializers.ImageField):
    """Поле для декодирования изображений из Base64."""

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f'temp.{ext}')
        return super().to_internal_value(data)


class CustomUserViewSet(UserViewSet):
    """Вьюсет пользователей с подписками и управлением аватаром."""
    @action(
        ["get", "put", "patch", "delete"],
        detail=False,
        permission_classes=[IsAuthenticated]
    )
    def me(self, request, *args, **kwargs):
        """Обработка эндпоинта /me с защитой от анонимных пользователей."""
        if request.user.is_anonymous:
            return Response(
                {"detail": "Учетные данные не были предоставлены."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
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
        if "avatar" not in request.data or not request.data["avatar"]:
            return Response(
                {"avatar": "Это поле обязательно и не должно быть пустым."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        class AvatarSerializer(serializers.ModelSerializer):
            avatar = Base64ImageField(required=True)

            class Meta:
                model = User
                fields = ("avatar",)

        serializer = AvatarSerializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"avatar": request.build_absolute_uri(user.avatar.url)},
            status=status.HTTP_200_OK,
        )

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
    def subscribe(self, request: Request, id: int = None) -> Response:
        """Подписка или отписка от автора."""
        author = get_object_or_404(User, id=id)
        user = request.user

        if request.method == "POST":
            return self._create_subscription(user, author, request)

        return self._delete_subscription(user, author)

    def _create_subscription(self, user, author, request: Request) -> Response:
        """Обработка создания подписки."""
        if user == author:
            return Response(
                {"errors": "Вы не можете подписаться на самого себя."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Subscription.objects.filter(user=user, author=author).exists():
            return Response(
                {"errors": "Вы уже подписаны на этого автора."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Subscription.objects.create(user=user, author=author)
        serializer = SubscriptionSerializer(
            author, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _delete_subscription(self, user, author) -> Response:
        """Обработка удаления подписки."""
        subscription = Subscription.objects.filter(user=user, author=author)

        if not subscription.exists():
            return Response(
                {"errors": "Вы не подписаны на этого автора."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет для просмотра тегов без пагинации."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        """Возвращает список тегов без пагинации."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет для просмотра ингредиентов без пагинации."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [AllowAny]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
    pagination_class = None

    def list(self, request, *args, **kwargs):
        """Возвращает список ингредиентов без пагинации."""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RecipeViewSet(viewsets.ModelViewSet):
    """Вьюсет для CRUD операций с рецептами."""

    queryset = Recipe.objects.all()
    permission_classes = [IsAuthorOrReadOnly]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        """Возвращает соответствующий сериализатор для действия."""
        if self.action in ("list", "retrieve"):
            return RecipeReadSerializer
        return RecipeWriteSerializer

    def _validate_pk(self, pk: int) -> int:
        """Проверяет и возвращает целочисленный первичный ключ."""
        if pk is None or not str(pk).isdigit():
            return None
        return int(pk)

    def _manage_relation(
        self, request: Request, model, pk: int = None
    ) -> Response:
        """Общий обработчик для избранного и корзины покупок."""
        validated_pk = self._validate_pk(pk)
        if validated_pk is None:
            return Response(
                {"errors": "Рецепт не найден (невалидный ID)."},
                status=status.HTTP_404_NOT_FOUND,
            )

        recipe = get_object_or_404(Recipe, id=validated_pk)
        user = request.user

        if request.method == "POST":
            return self._add_relation(model, user, recipe, request)

        return self._remove_relation(model, user, recipe)

    def _add_relation(self, model, user, recipe, request: Request) -> Response:
        """Добавляет рецепт в избранное или корзину пользователя."""
        if model.objects.filter(user=user, recipe=recipe).exists():
            return Response(
                {"errors": "Рецепт уже добавлен в этот список."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        model.objects.create(user=user, recipe=recipe)
        serializer = CompactRecipeSerializer(
            recipe, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _remove_relation(self, model, user, recipe) -> Response:
        """Удаляет рецепт из избранного или корзины пользователя."""
        relation = model.objects.filter(user=user, recipe=recipe)

        if not relation.exists():
            return Response(
                {"errors": "Рецепта нет в этом списке."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        relation.delete()
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
    def get_link(self, request: Request, pk: int = None) -> Response:
        """Генерирует короткую ссылку на рецепт."""
        validated_pk = self._validate_pk(pk)
        if validated_pk is None:
            return Response(
                {"errors": "Рецепт не найден (невалидный ID)."},
                status=status.HTTP_404_NOT_FOUND,
            )

        recipe = get_object_or_404(Recipe, id=validated_pk)
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
            lines.append(
                f"• {ing['ingredient__name']} — "
                f"{ing['total_amount']} {
                    ing['ingredient__measurement_unit']
                }\n"
            )

        return "".join(lines)
