import base64
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from djoser.serializers import UserCreateSerializer, UserSerializer
from rest_framework import serializers

from apps.recipes.models import (
    Favorite, Ingredient, Recipe, RecipeIngredient, ShoppingCart, Tag
)
from apps.users.models import Subscription

User = get_user_model()


# =====================================================================
# СЛУЖЕБНЫЕ ПОЛЯ (CUSTOM FIELDS)
# =====================================================================

class Base64ImageField(serializers.ImageField):
    """Декодер Base64-строк в файлы изображений для рецептов."""

    def to_internal_value(self, data: Any) -> Any:
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f'temp.{ext}')
        return super().to_internal_value(data)


# =====================================================================
# СЕРИАЛИЗАТОРЫ ПОЛЬЗОВАТЕЛЕЙ И ПОДПИСОК (USERS & SUBSCRIPTIONS)
# =====================================================================

class CustomUserCreateSerializer(UserCreateSerializer):
    """Кастомный сериализатор для регистрации новых пользователей."""

    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = (
            'email', 'id', 'username', 'first_name', 'last_name', 'password'
        )


class CustomUserSerializer(UserSerializer):
    """Сериализатор профиля пользователя с флагом подписки."""

    is_subscribed = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        model = User
        fields = (
            'email', 'id', 'username', 'first_name',
            'last_name', 'is_subscribed'
        )

    def get_is_subscribed(self, obj: User) -> bool:
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False
        return Subscription.objects.filter(
            user=request.user, author=obj
        ).exists()


class SubscriptionSerializer(CustomUserSerializer):
    """Сериализатор для выгрузки авторов, на которых подписан пользователь."""

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(
        source='recipes.count', read_only=True
    )

    class Meta(CustomUserSerializer.Meta):
        fields = CustomUserSerializer.Meta.fields + (
            'recipes', 'recipes_count'
        )
        read_only_fields = ('email', 'username', 'first_name', 'last_name')

    def get_recipes(self, obj: User) -> List[Dict[str, Any]]:
        request = self.context.get('request')
        recipes = obj.recipes.all()
        if request:
            limit = request.query_params.get('recipes_limit')
            if limit and limit.isdigit():
                recipes = recipes[:int(limit)]
        return CompactRecipeSerializer(
            recipes, many=True, context={'request': request}
        ).data


# =====================================================================
# СЕРИАЛИЗАТОРЫ СУЩНОСТЕЙ РЕЦЕПТОВ (TAGS & INGREDIENTS)
# =====================================================================

class TagSerializer(serializers.ModelSerializer):
    """Сериализатор для работы с тегами."""

    class Meta:
        model = Tag
        fields = ('id', 'name', 'color', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения ингредиентов."""

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    """Сериализатор для отображения ингредиентов внутри рецепта."""

    id = serializers.IntegerField(source='ingredient.id')
    name = serializers.CharField(source='ingredient.name')
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeIngredientWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для сохранения ингредиентов при создании рецепта."""

    id = serializers.IntegerField()
    amount = serializers.IntegerField()

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'amount')


# =====================================================================
# СЕРИАЛИЗАТОРЫ РЕЦЕПТОВ (RECIPES CRUD)
# =====================================================================

class CompactRecipeSerializer(serializers.ModelSerializer):
    """Укороченный сериализатор рецептов для списков покупок и подписок."""

    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id', 'name', 'image', 'cooking_time')


class RecipeReadSerializer(serializers.ModelSerializer):
    """Основной сериализатор для безопасного чтения рецептов (Safe Methods)."""

    tags = TagSerializer(many=True, read_only=True)
    author = CustomUserSerializer(read_only=True)
    ingredients = RecipeIngredientReadSerializer(
        many=True, source='recipe_ingredients', read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients', 'is_favorited',
            'is_in_shopping_cart', 'name', 'image', 'text', 'cooking_time'
        )

    def _check_relation(self, obj: Recipe, model: Any) -> bool:
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False
        return model.objects.filter(user=request.user, recipe=obj).exists()

    def get_is_favorited(self, obj: Recipe) -> bool:
        return self._check_relation(obj, Favorite)

    def get_is_in_shopping_cart(self, obj: Recipe) -> bool:
        return self._check_relation(obj, ShoppingCart)


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания, изменения и удаления рецептов."""

    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True
    )
    author = CustomUserSerializer(read_only=True)
    ingredients = RecipeIngredientWriteSerializer(many=True)
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients',
            'name', 'image', 'text', 'cooking_time'
        )

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        ingredients = data.get('ingredients')
        if not ingredients:
            raise serializers.ValidationError(
                {'ingredients': 'Рецепт не может быть без ингредиентов.'}
            )

        ing_ids = [ing['id'] for ing in ingredients]
        if len(ing_ids) != len(set(ing_ids)):
            raise serializers.ValidationError(
                {'ingredients': 'Ингредиенты в рецепте не должны повторяться.'}
            )

        tags = data.get('tags')
        if not tags:
            raise serializers.ValidationError(
                {'tags': 'Рецепт должен содержать хотя бы один тег.'}
            )
        if len(tags) != len(set(tags)):
            raise serializers.ValidationError(
                {'tags': 'Теги в рецепте не должны повторяться.'}
            )

        return data

    def _save_ingredients(
        self, recipe: Recipe, ingredients: List[Dict[str, Any]]
    ) -> None:
        RecipeIngredient.objects.bulk_create([
            RecipeIngredient(
                recipe=recipe,
                ingredient_id=ing['id'],
                amount=ing['amount']
            ) for ing in ingredients
        ])

    def create(self, validated_data: Dict[str, Any]) -> Recipe:
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('ingredients')

        recipe = Recipe.objects.create(
            author=self.context['request'].user,
            **validated_data
        )
        recipe.tags.set(tags)
        self._save_ingredients(recipe, ingredients)
        return recipe

    def update(
        self, instance: Recipe, validated_data: Dict[str, Any]
    ) -> Recipe:
        tags = validated_data.pop('tags', None)
        ingredients = validated_data.pop('ingredients', None)

        instance = super().update(instance, validated_data)

        if tags is not None:
            instance.tags.set(tags)
        if ingredients is not None:
            instance.recipe_ingredients.all().delete()
            self._save_ingredients(instance, ingredients)

        return instance

    def to_representation(self, instance: Recipe) -> Dict[str, Any]:
        return RecipeReadSerializer(
            instance, context={'request': self.context.get('request')}
        ).data
