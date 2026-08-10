from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

User = get_user_model()


class Tag(models.Model):
    """Модель тега для рецептов (Завтрак, Обед, Ужин и т.д.)."""

    name = models.CharField(
        'Название тега',
        max_length=200,
        unique=True,
    )
    color = models.CharField(
        'Цвет в HEX',
        max_length=7,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$',
                message='Поле должно содержать валидный HEX-код цвета.'
            )
        ]
    )
    slug = models.SlugField(
        'Уникальный слаг',
        max_length=200,
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
        max_length=200,
    )
    measurement_unit = models.CharField(
        'Единица измерения',
        max_length=200,
    )

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'measurement_unit'],
                name='unique_ingredient_name_unit'
            )
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.measurement_unit})'


class Recipe(models.Model):
    """Модель рецепта — центральная сущность системы."""

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recipes',
        verbose_name='Автор рецепта',
    )
    name = models.CharField(
        'Название рецепта',
        max_length=200,
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
                1, message='Время приготовления не может быть меньше 1 минуты.'
            )
        ]
    )
    pub_date = models.DateTimeField(
        'Дата публикации',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        # Требование ТЗ: новые рецепты должны быть выше в списке
        ordering = ['-pub_date']

    def __str__(self) -> str:
        return self.name


class RecipeIngredient(models.Model):
    """
    Промежуточная таблица, связывающая Рецепт и Ингредиент (с количеством).
    """

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
                1, message='Количество ингредиента не может быть меньше 1.'
            )
        ]
    )

    class Meta:
        verbose_name = 'Ингредиент в рецепте'
        verbose_name_plural = 'Ингредиенты в рецептах'
        constraints = [
            # DRY защита
            # нельзя добавить один и тот же ингредиент в рецепт дважды
            models.UniqueConstraint(
                fields=['recipe', 'ingredient'],
                name='unique_recipe_ingredient'
            )
        ]

    def __str__(self) -> str:
        return f'{self.recipe.name} — {self.ingredient.name} ({self.amount})'


class UserRecipeRelation(models.Model):
    """Абстрактная базовая модель для Избранного и Списка покупок (DRY)."""

    user = models.ForeignKey(
        User,
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

    def __str__(self) -> str:
        return f'{self.user.username} -> {self.recipe.name}'


class Favorite(UserRecipeRelation):
    """Модель избранных рецептов для пользователя."""

    class Meta(UserRecipeRelation.Meta):
        verbose_name = 'Избранный рецепт'
        verbose_name_plural = 'Избранные рецепты'
        default_related_name = 'favorites'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_favorite_recipe'
            )
        ]


class ShoppingCart(UserRecipeRelation):
    """Модель списка покупок пользователя."""

    class Meta(UserRecipeRelation.Meta):
        verbose_name = 'Рецепт в списке покупок'
        verbose_name_plural = 'Рецепты в списках покупок'
        default_related_name = 'shopping_cart'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_shopping_cart_recipe'
            )
        ]
