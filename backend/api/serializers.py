from django.contrib.auth import get_user_model
from rest_framework import serializers

from api.fields import Base64ImageField
from apps.recipes.models import Ingredient, Recipe, RecipeIngredient, Tag
from apps.users.models import Subscription

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор профиля пользователя."""

    is_subscribed = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username', 'first_name',
            'last_name', 'is_subscribed', 'avatar',
        )

    def get_is_subscribed(self, obj):
        """Проверяет, подписан ли текущий пользователь на автора."""
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False
        return Subscription.objects.filter(
            user=request.user, author=obj
        ).exists()

    def get_avatar(self, obj):
        """Возвращает URL аватара пользователя."""
        if obj.avatar:
            return obj.avatar.url
        return None


class SubscriptionSerializer(UserSerializer):
    """Сериализатор для подписок с рецептами автора."""

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(
        source='recipes.count', read_only=True
    )

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('recipes', 'recipes_count')
        read_only_fields = (
            'email', 'username', 'first_name', 'last_name', 'avatar'
        )

    def get_recipes(self, obj):
        """Возвращает рецепты автора с учетом параметра recipes_limit."""
        request = self.context.get('request')
        recipes = obj.recipes.all()

        if request:
            limit = request.query_params.get('recipes_limit')
            if limit and limit.isdigit():
                recipes = recipes[:int(limit)]

        return CompactRecipeSerializer(
            recipes, many=True, context={'request': request}
        ).data


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор для тегов."""

    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для ингредиентов."""

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class RecipeIngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для ингредиентов в рецепте."""

    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        source='ingredient',
    )
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class CompactRecipeSerializer(serializers.ModelSerializer):
    """Облегченный сериализатор рецептов для списков."""

    image = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id', 'name', 'image', 'cooking_time')

    def get_image(self, obj):
        """Возвращает URL изображения рецепта."""
        if obj.image:
            return obj.image.url
        return None


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения рецептов."""

    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        many=True, source='recipe_ingredients', read_only=True
    )
    is_favorited = serializers.BooleanField()
    is_in_shopping_cart = serializers.BooleanField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients',
            'is_favorited', 'is_in_shopping_cart',
            'name', 'image', 'text', 'cooking_time',
        )

    def get_image(self, obj):
        """Возвращает URL изображения рецепта."""
        if obj.image:
            return obj.image.url
        return None


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления рецептов."""

    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True
    )
    ingredients = RecipeIngredientSerializer(many=True)
    image = Base64ImageField(required=True)

    class Meta:
        model = Recipe
        fields = (
            'ingredients', 'tags', 'image', 'name', 'text', 'cooking_time'
        )

    def validate_image(self, value):
        """Проверяет наличие изображения."""
        if not value:
            raise serializers.ValidationError('Это поле обязательно.')
        return value

    def validate(self, data):
        """Основная валидация для создания рецептов."""
        ingredients = data.get('ingredients')
        if not ingredients:
            raise serializers.ValidationError(
                {'ingredients': 'Должен быть хотя бы один ингредиент.'}
            )

        ingredient_ids = [item['ingredient'].id for item in ingredients]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                {'ingredients': 'Ингредиенты не должны повторяться.'}
            )

        tags = data.get('tags')
        if not tags:
            raise serializers.ValidationError(
                {'tags': 'Должен быть выбран хотя бы один тег.'}
            )

        if len(tags) != len(set(tags)):
            raise serializers.ValidationError(
                {'tags': 'Теги не должны повторяться.'}
            )

        return data

    def _save_ingredients(self, recipe, ingredients_data):
        """Сохраняет ингредиенты для рецепта."""
        RecipeIngredient.objects.bulk_create([
            RecipeIngredient(
                recipe=recipe,
                ingredient=item['ingredient'],
                amount=item['amount'],
            ) for item in ingredients_data
        ])

    def create(self, validated_data):
        """Создает новый рецепт."""
        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')

        author = self.context['request'].user
        recipe = Recipe.objects.create(author=author, **validated_data)

        recipe.tags.set(tags_data)
        self._save_ingredients(recipe, ingredients_data)

        return recipe

    def update(self, instance, validated_data):
        """Обновляет существующий рецепт."""
        ingredients_data = validated_data.pop('ingredients', None)
        tags_data = validated_data.pop('tags', None)

        if tags_data is not None:
            instance.tags.clear()
            instance.tags.set(tags_data)

        if ingredients_data is not None:
            instance.recipe_ingredients.all().delete()
            self._save_ingredients(instance, ingredients_data)

        return super().update(instance, validated_data)

    def to_representation(self, instance):
        """Возвращает сериализованное представление рецепта."""
        return RecipeReadSerializer(instance, context=self.context).data


class AvatarSerializer(serializers.ModelSerializer):
    """Сериализатор для загрузки аватара."""

    avatar = Base64ImageField(required=True)

    class Meta:
        model = User
        fields = ('avatar',)
