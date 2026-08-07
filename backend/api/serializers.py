import base64
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from djoser.serializers import UserCreateSerializer, UserSerializer
from rest_framework import serializers

from apps.recipes.models import Favorite, Ingredient, Recipe, RecipeIngredient, ShoppingCart, Tag
from apps.users.models import Subscription

User = get_user_model()


# =====================================================================
# КАСТОМНЫЕ ПОЛЯ (CUSTOM FIELDS)
# =====================================================================

class Base64ImageField(serializers.ImageField):
    """Кастомное поле для декодирования изображений из Base64 формата."""

    def to_internal_value(self, data: Any) -> ContentFile:
        if isinstance(data, str) and data.startswith('data:image'):
            format_str, img_str = data.split(';base64,')
            ext = format_str.split('/')[-1]
            data = ContentFile(base64.b64decode(img_str), name=f'temp.{ext}')
        return super().to_internal_value(data)


# =====================================================================
# СЕРИАЛИЗАТОРЫ ПОЛЬЗОВАТЕЛЕЙ И ПОДПИСОК (USERS & SUBSCRIPTIONS)
# =====================================================================

class CustomUserCreateSerializer(UserCreateSerializer):
    """Сериализатор для регистрации нового пользователя."""

    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name', 'password')


class CustomUserSerializer(UserSerializer):
    """Сериализатор для профиля пользователя с проверкой подписки."""

    is_subscribed = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name', 'is_subscribed', 'avatar')

    def get_is_subscribed(self, obj: User) -> bool:
        """Проверяет, подписан ли текущий пользователь на данного автора."""
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False
        return Subscription.objects.filter(user=request.user, author=obj).exists()


class SubscriptionSerializer(CustomUserSerializer):
    """Сериализатор для отображения авторов, на которых подписан пользователь."""

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.ReadOnlyField(source='recipes.count')

    class Meta(CustomUserSerializer.Meta):
        fields = CustomUserSerializer.Meta.fields + ('recipes', 'recipes_count')

    def get_recipes(self, obj: User) -> List[Dict[str, Any]]:
        """Возвращает список рецептов автора с учетом параметра лимита."""
        request = self.context.get('request')
        recipes = obj.recipes.all()
        
        if request:
            limit = request.query_params.get('recipes_limit')
            if limit and limit.isdigit():
                recipes = recipes[:int(limit)]
                
        context = {'request': request}
        return CompactRecipeSerializer(recipes, many=True, context=context).data


# =====================================================================
# СЕРИАЛИЗАТОРЫ СУЩНОСТЕЙ РЕЦЕПТОВ (RECIPES CORE)
# =====================================================================

class TagSerializer(serializers.ModelSerializer):
    """Сериализатор для тегов."""

    class Meta:
        model = Tag
        fields = ('id', 'name', 'color', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для ингредиентов."""

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения ингредиентов внутри рецепта."""

    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(source='ingredient.measurement_unit')

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeIngredientWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для записи ингредиентов при создании/редактировании рецепта."""

    id = serializers.IntegerField()

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'amount')


class CompactRecipeSerializer(serializers.ModelSerializer):
    """Облегченный сериализатор рецептов для списков подписок и избранного."""

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id', 'name', 'image', 'cooking_time')


# =====================================================================
# ОСНОВНЫЕ СЕРИАЛИЗАТОРЫ РЕЦЕПТОВ (READ & WRITE)
# =====================================================================

class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для безопасного чтения рецептов (GET)."""

    tags = TagSerializer(many=True, read_only=True)
    author = CustomUserSerializer(read_only=True)
    ingredients = RecipeIngredientReadSerializer(source='recipe_ingredients', many=True, read_only=True)
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients', 'is_favorited',
            'is_in_shopping_cart', 'name', 'image', 'text', 'cooking_time'
        )

    def _user_relation_exists(self, obj: Recipe, model: Any) -> bool:
        """DRY утилита для проверки связей списков пользователя с рецептом."""
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False
        return model.objects.filter(user=request.user, recipe=obj).exists()

    def get_is_favorited(self, obj: Recipe) -> bool:
        return self._user_relation_exists(obj, Favorite)

    def get_is_in_shopping_cart(self, obj: Recipe) -> bool:
        return self._user_relation_exists(obj, ShoppingCart)


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления рецептов (POST, PATCH)."""

    tags = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), many=True)
    ingredients = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all(), many=True) # Исправим для валидности связей
    ingredients = RecipeIngredientWriteSerializer(many=True)
    image = Base64ImageField()
    author = CustomUserSerializer(read_only=True)

    class Meta:
        model = Recipe
        fields = ('ingredients', 'tags', 'image', 'name', 'text', 'cooking_time', 'author')

    def validate_ingredients(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not value:
            raise serializers.ValidationError('Должен быть как минимум один ингредиент.')
        ingredients_ids = [item['id'] for item in value]
        if len(ingredients_ids) != len(set(ingredients_ids)):
            raise serializers.ValidationError('Ингредиенты в рецепте не должны повторяться.')
        return value

    def validate_tags(self, value: List[Tag]) -> List[Tag]:
        if not value:
            raise serializers.ValidationError('Должен быть выбран хотя бы один тег.')
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Теги не должны повторяться.')
        return value

    def _save_ingredients(self, recipe: Recipe, ingredients_data: List[Dict[str, Any]]) -> None:
        """Оптимизация bulk_create для исключения N+1 запросов при записи связей."""
        RecipeIngredient.objects.bulk_create([
            RecipeIngredient(
                recipe=recipe,
                ingredient_id=ingredient['id'],
                amount=ingredient['amount']
            ) for ingredient in ingredients_data
        ])

    @transaction.atomic
    def create(self, validated_data: Dict[str, Any]) -> Recipe:
        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')
        
        recipe = Recipe.objects.create(author=self.context['request'].user, **validated_data)
        recipe.tags.set(tags_data)
        self._save_ingredients(recipe, ingredients_data)
        return recipe

    @transaction.atomic
    def update(self, instance: Recipe, validated_data: Dict[str, Any]) -> Recipe:
        ingredients_data = validated_data.pop('ingredients', None)
        tags_data = validated_data.pop('tags', None)

        instance = super().update(instance, validated_data)

        if tags_data is not None:
            instance.tags.set(tags_data)
        if ingredients_data is not None:
            instance.recipe_ingredients.all().delete()
            self._save_ingredients(instance, ingredients_data)

        return instance

    def to_representation(self, instance: Recipe) -> Dict[str, Any]:
        return RecipeReadSerializer(instance, context=self.context).data
