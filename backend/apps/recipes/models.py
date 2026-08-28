from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.recipes.constants import (
    INGREDIENT_MAX_LENGTH,
    INGREDIENT_UNIT_MAX_LENGTH,
    MAX_COOKING_TIME,
    MAX_INGREDIENT_AMOUNT,
    RECIPE_NAME_MAX_LENGTH,
    SLUG_MAX_LENGTH,
    TAG_NAME_MAX_LENGTH,
    MINIMUM_COOKING_TIME
)

User = get_user_model()


class Tag(models.Model):
    """Модель тега для рецептов."""

    name = models.CharField(
        'Название тега',
        max_length=TAG_NAME_MAX_LENGTH,
        unique=True,
    )
    slug = models.SlugField(
        'Уникальный слаг',
        max_length=SLUG_MAX_LENGTH,
        unique=True,
    )

    class Meta:
        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Ingredient(models.Model):
    """Модель ингредиента."""

    name = models.CharField(
        'Название ингредиента',
        max_length=INGREDIENT_MAX_LENGTH,
    )
    measurement_unit = models.CharField(
        'Единица измерения',
        max_length=INGREDIENT_UNIT_MAX_LENGTH,
    )

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'measurement_unit'],
                name='unique_ingredient_name_unit',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.measurement_unit})'


class Recipe(models.Model):
    """Модель рецепта."""

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recipes',
        verbose_name='Автор рецепта',
    )
    name = models.CharField(
        'Название рецепта',
        max_length=RECIPE_NAME_MAX_LENGTH,
    )
    image = models.ImageField(
        'Изображение рецепта',
        upload_to='recipes/images/',
    )
    text = models.TextField(
        'Описание рецепта',
    )
    ingredients = models.ManyToManyField(
        Ingredient,
        through='RecipeIngredient',
        related_name='recipes',
        verbose_name='Список ингредиентов',
    )
    tags = models.ManyToManyField(
        Tag,
        related_name='recipes',
        verbose_name='Теги',
    )
    cooking_time = models.PositiveSmallIntegerField(
        'Время приготовления (в минутах)',
        validators=[
            MinValueValidator(
                MINIMUM_COOKING_TIME,
                message='Время приготовления не может быть меньше 1 минуты.',
            ),
            MaxValueValidator(
                MAX_COOKING_TIME,
                message=(
                    f'Время приготовления не может б. {MAX_COOKING_TIME}минут.'
                ),
            ),
        ],
    )
    pub_date = models.DateTimeField(
        'Дата публикации',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        ordering = ['-pub_date']

    def __str__(self) -> str:
        return self.name


class RecipeIngredient(models.Model):
    """Связь рецепта с ингредиентом и его количеством."""

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='recipe_ingredients',
        verbose_name='Рецепт',
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name='ingredient_recipes',
        verbose_name='Ингредиент',
    )
    amount = models.PositiveSmallIntegerField(
        'Количество',
        validators=[
            MinValueValidator(
                MINIMUM_COOKING_TIME,
                message='Количество инг. не может быть меньше 1.',
            ),
            MaxValueValidator(
                MAX_INGREDIENT_AMOUNT,
                message=(
                    f'Количество инг. не может больше {MAX_INGREDIENT_AMOUNT}.'
                ),
            ),
        ],
    )

    class Meta:
        verbose_name = 'Инг. в рецепте'
        verbose_name_plural = 'Инг. в рецептах'
        constraints = [
            models.UniqueConstraint(
                fields=['recipe', 'ingredient'],
                name='unique_recipe_ingredient',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.recipe.name} — {self.ingredient.name} ({self.amount})'


class UserRecipeRelation(models.Model):
    """Абстрактная модель связи пользователя и рецепта."""

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
    )

    class Meta:
        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='%(app_label)s_%(class)s_unique',
            )
        ]

    def __str__(self):
        return f'{self.user.username} - {self.recipe.name}'


class Favorite(UserRecipeRelation):
    """Модель избранных рецептов."""

    class Meta(UserRecipeRelation.Meta):
        verbose_name = 'Избранный рецепт'
        verbose_name_plural = 'Избранные рецепты'
        default_related_name = 'favorite'


class ShoppingCart(UserRecipeRelation):
    """Модель корзины покупок."""

    class Meta(UserRecipeRelation.Meta):
        verbose_name = 'Корзина покупок'
        verbose_name_plural = 'Корзины покупок'
        default_related_name = 'shopping_cart'
