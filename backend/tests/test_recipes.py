from datetime import timedelta
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.utils import timezone

from apps.recipes.models import (
    Favorite, Ingredient, Recipe, RecipeIngredient, ShoppingCart, Tag
)

User = get_user_model()


@pytest.mark.django_db
class TestRecipesCoreModels:
    """Тестирование структуры моделей ядра рецептов, тегов и ингредиентов."""

    @pytest.fixture
    def setup_data(self):
        """Создание базовых сущностей для тестов."""
        author = User.objects.create_user(
            username='chef_test', email='chef_test@foodgram.com'
        )
        tag = Tag.objects.create(
            name='Завтрак', color='#E26C2D', slug='breakfast'
        )
        ingredient = Ingredient.objects.create(
            name='Сахар', measurement_unit='г'
        )
        return author, tag, ingredient

    def test_tag_creation(self):
        """Проверка валидности создания тегов."""
        tag = Tag.objects.create(name='Обед', color='#49B64E', slug='dinner')
        assert str(tag) == 'Обед'
        assert tag.slug == 'dinner'

    def test_ingredient_creation(self):
        """Проверка валидности создания ингредиентов."""
        ing = Ingredient.objects.create(name='Молоко', measurement_unit='мл')
        assert str(ing) == 'Молоко (мл)'

    def test_recipe_creation_and_ordering(self, setup_data):
        """Проверка создания рецепта и сортировки (новые выше)."""
        author, tag, ingredient = setup_data

        # Создаем первый рецепт
        recipe1 = Recipe.objects.create(
            author=author,
            name='Яичница',
            text='Простой рецепт яичницы',
            cooking_time=5
        )
        # Искусственно сдвигаем дату публикации первого рецепта в прошлое
        Recipe.objects.filter(id=recipe1.id).update(
            pub_date=timezone.now() - timedelta(hours=1)
        )

        # Создаем второй рецепт (он будет считаться более новым)
        recipe2 = Recipe.objects.create(
            author=author,
            name='Блины',
            text='Рецепт блинов',
            cooking_time=15
        )

        # Проверяем Meta-сортировку:
        # Блины созданы позже, они должны быть первыми
        recipes = list(Recipe.objects.all())
        assert recipes[0] == recipe2
        assert recipes[1] == recipe1
        assert str(recipe1) == 'Яичница'

    def test_cooking_time_validation(self, setup_data):
        """Бизнес-логика: время приготовления не может быть меньше 1."""
        author, _, _ = setup_data

        recipe = Recipe(
            author=author,
            name='Странное блюдо',
            text='Текст',
            cooking_time=0  # Невалидное значение
        )
        with pytest.raises((ValidationError, IntegrityError)):
            recipe.full_clean()
            recipe.save()


@pytest.mark.django_db
class TestRecipeIngredientsAndConstraints:
    """Тестирование промежуточных связей и ограничений целостности данных."""

    def test_recipe_ingredient_min_amount(self):
        """Бизнес-логика: количество ингредиента не может быть меньше 1."""
        author = User.objects.create_user(
            username='chef_2', email='c2@test.com'
        )
        recipe = Recipe.objects.create(
            author=author, name='Суп', text='Код', cooking_time=10
        )
        ingredient = Ingredient.objects.create(
            name='Соль', measurement_unit='г'
        )

        recipe_ing = RecipeIngredient(
            recipe=recipe,
            ingredient=ingredient,
            amount=0  # Невалидное значение
        )
        with pytest.raises((ValidationError, IntegrityError)):
            recipe_ing.full_clean()
            recipe_ing.save()

    def test_unique_ingredient_in_recipe_constraint(self):
        """DRY: Нельзя добавить один и тот же ингредиент в рецепт дважды."""
        author = User.objects.create_user(
            username='chef_3', email='c3@test.com'
        )
        recipe = Recipe.objects.create(
            author=author, name='Каша', text='Код', cooking_time=10
        )
        ingredient = Ingredient.objects.create(
            name='Вода', measurement_unit='л'
        )

        RecipeIngredient.objects.create(
            recipe=recipe, ingredient=ingredient, amount=2
        )

        # Повторное добавление падает на уровне IntegrityError базы данных
        with pytest.raises(IntegrityError):
            RecipeIngredient.objects.create(
                recipe=recipe, ingredient=ingredient, amount=1
            )


@pytest.mark.django_db
class TestUserListsModels:
    """Тестирование моделей Избранного и Списка покупок."""

    @pytest.fixture
    def setup_recipe(self):
        user = User.objects.create_user(
            username='user_list', email='ul@test.com'
        )
        author = User.objects.create_user(
            username='chef_list', email='cl@test.com'
        )
        recipe = Recipe.objects.create(
            author=author, name='Салат', text='Код', cooking_time=5
        )
        return user, recipe

    def test_favorite_uniqueness(self, setup_recipe):
        """Проверка ограничений уникальности для Избранного."""
        user, recipe = setup_recipe
        Favorite.objects.create(user=user, recipe=recipe)

        with pytest.raises(IntegrityError):
            Favorite.objects.create(user=user, recipe=recipe)

    def test_shopping_cart_uniqueness(self, setup_recipe):
        """Проверка ограничений уникальности для Списка покупок."""
        user, recipe = setup_recipe
        ShoppingCart.objects.create(user=user, recipe=recipe)

        with pytest.raises(IntegrityError):
            ShoppingCart.objects.create(user=user, recipe=recipe)
