import base64
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from rest_framework import serializers

from apps.recipes.models import Ingredient, Recipe, RecipeIngredient, Tag
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


class CustomUserCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для регистрации пользователей."""

    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def validate(self, attrs):
        first_name = attrs.get('first_name', '').strip()
        last_name = attrs.get('last_name', '').strip()

        if not first_name:
            raise serializers.ValidationError(
                {'first_name': 'Это поле не может быть пустым.'}
            )

        if not last_name:
            raise serializers.ValidationError(
                {'last_name': 'Это поле не может быть пустым.'}
            )

        return super().validate(attrs)

    def create(self, validated_data):
        user = User(
            email=validated_data['email'],
            username=validated_data['username'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


class CustomUserSerializer(serializers.ModelSerializer):
    """Сериализатор профиля пользователя."""

    is_subscribed = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username', 'first_name',
            'last_name', 'is_subscribed', 'avatar',
        )

    def get_is_subscribed(self, obj: User) -> bool:
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False
        return Subscription.objects.filter(user=request.user, author=obj).exists()

    def get_avatar(self, obj: User) -> str | None:
        if obj.avatar:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class SubscriptionSerializer(CustomUserSerializer):
    """Сериализатор для подписок с рецептами автора."""

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(source='recipes.count', read_only=True)

    class Meta(CustomUserSerializer.Meta):
        fields = CustomUserSerializer.Meta.fields + ('recipes', 'recipes_count')
        read_only_fields = ('email', 'username', 'first_name', 'last_name', 'avatar')

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


class TagPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """Поле для тегов с приведением ID к числу."""

    def to_internal_value(self, data):
        try:
            return super().to_internal_value(int(data))
        except (ValueError, TypeError):
            raise serializers.ValidationError('ID тега должно быть числом.')


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


class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения ингредиентов в рецепте."""

    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(source='ingredient.measurement_unit')

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeIngredientWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для записи ингредиентов в рецепте."""

    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.IntegerField()

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'amount')


class CompactRecipeSerializer(serializers.ModelSerializer):
    """Облегченный сериализатор рецептов для списков."""

    image = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id', 'name', 'image', 'cooking_time')

    def get_image(self, obj: Recipe) -> str | None:
        if obj.image:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения рецептов."""

    tags = TagSerializer(many=True, read_only=True)
    author = CustomUserSerializer(read_only=True)
    ingredients = RecipeIngredientReadSerializer(
        many=True, source='recipe_ingredients', read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients',
            'is_favorited', 'is_in_shopping_cart',
            'name', 'image', 'text', 'cooking_time',
        )

    def _check_relation(self, obj: Recipe, model) -> bool:
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False
        return model.objects.filter(user=request.user, recipe=obj).exists()

    def get_is_favorited(self, obj: Recipe) -> bool:
        from apps.recipes.models import Favorite
        return self._check_relation(obj, Favorite)

    def get_is_in_shopping_cart(self, obj: Recipe) -> bool:
        from apps.recipes.models import ShoppingCart
        return self._check_relation(obj, ShoppingCart)

    def get_image(self, obj: Recipe) -> str | None:
        if obj.image:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления рецептов."""

    tags = TagPrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )
    ingredients = RecipeIngredientWriteSerializer(many=True, required=False)
    image = Base64ImageField(required=False)
    cooking_time = serializers.IntegerField(required=False)

    class Meta:
        model = Recipe
        fields = ('ingredients', 'tags', 'image', 'name', 'text', 'cooking_time')

    def validate_cooking_time(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError(
                'Время приготовления должно быть не меньше 1 минуты.'
            )
        return value

    def validate_ingredients(self, ingredients_data):
        if not ingredients_data:
            raise serializers.ValidationError(
                'Должен быть хотя бы один ингредиент.'
            )

        ingredient_ids = []
        for item in ingredients_data:
            ingredient_obj = item.get('id')
            if ingredient_obj is None:
                raise serializers.ValidationError('Неверный ID ингредиента.')

            amount = item.get('amount')
            if amount is not None and int(amount) < 1:
                raise serializers.ValidationError(
                    'Количество ингредиента должно быть больше 0.'
                )

            if ingredient_obj.id in ingredient_ids:
                raise serializers.ValidationError(
                    'Ингредиенты не должны повторяться.'
                )

            ingredient_ids.append(ingredient_obj.id)

        return ingredients_data

    def validate_tags(self, tags_data):
        if not tags_data:
            raise serializers.ValidationError(
                'Должен быть выбран хотя бы один тег.'
            )

        if len(tags_data) != len(set(tags_data)):
            raise serializers.ValidationError('Теги не должны повторяться.')

        return tags_data

    def validate(self, data):
        """Основная валидация для создания и обновления."""
        if self.instance is None:
            # Создание рецепта — все поля обязательны
            required_fields = [
                'ingredients', 'tags', 'image',
                'name', 'text', 'cooking_time',
            ]

            for field in required_fields:
                if field not in data or not data[field]:
                    raise serializers.ValidationError(
                        {field: 'Это поле обязательно.'}
                    )

            self.validate_ingredients(data.get('ingredients'))
            self.validate_tags(data.get('tags'))

        else:
            # Обновление рецепта — проверяем только переданные поля
            if 'ingredients' in data:
                self.validate_ingredients(data.get('ingredients'))
            else:
                raise serializers.ValidationError(
                    {'ingredients': 'Это поле обязательно.'}
                )

            if 'tags' in data:
                self.validate_tags(data.get('tags'))
            else:
                raise serializers.ValidationError(
                    {'tags': 'Это поле обязательно.'}
                )

        return data

    def _save_ingredients(self, recipe: Recipe, ingredients_data: List[Dict[str, Any]]) -> None:
        """Сохраняет ингредиенты для рецепта."""
        RecipeIngredient.objects.bulk_create([
            RecipeIngredient(
                recipe=recipe,
                ingredient=item['id'],
                amount=item['amount'],
            ) for item in ingredients_data
        ])

    def create(self, validated_data):
        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')

        author = self.context['request'].user
        recipe = Recipe.objects.create(author=author, **validated_data)

        recipe.tags.set(tags_data)
        self._save_ingredients(recipe, ingredients_data)

        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')

        instance = super().update(instance, validated_data)

        instance.tags.set(tags_data)

        RecipeIngredient.objects.filter(recipe=instance).delete()
        self._save_ingredients(instance, ingredients_data)

        instance.refresh_from_db()
        return instance

    def to_representation(self, instance):
        return RecipeReadSerializer(instance, context=self.context).data
