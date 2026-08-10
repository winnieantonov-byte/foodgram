import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.recipes.models import (
    Favorite, Ingredient, Recipe, RecipeIngredient, ShoppingCart, Tag
)

User = get_user_model()


@pytest.mark.django_db
class TestRecipesAPI:
    """Интеграционные тесты для API рецептов, тегов и ингредиентов."""

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client_anon = APIClient()
        self.client_auth = APIClient()

        # Создаем пользователей
        self.author = User.objects.create_user(
            username='chef_api',
            email='chef_api@test.com',
            password='password123'
        )
        self.user = User.objects.create_user(
            username='user_api',
            email='user_api@test.com',
            password='password123'
        )

        # Авторизуем пользователя токеном
        token = Token.objects.create(user=self.user)
        self.client_auth.credentials(
            HTTP_AUTHORIZATION=f'Token {token.key}'
        )

        # Создаем теги и ингредиенты
        self.tag_breakfast = Tag.objects.create(
            name='Завтрак', color='#E26C2D', slug='breakfast'
        )
        self.tag_lunch = Tag.objects.create(
            name='Обед', color='#49B64E', slug='lunch'
        )
        self.ing_sugar = Ingredient.objects.create(
            name='Сахар', measurement_unit='г'
        )

        # Создаем базовый рецепт от автора
        self.recipe = Recipe.objects.create(
            author=self.author,
            name='Сладкий чай',
            text='Смешать чай и сахар',
            cooking_time=5
        )
        self.recipe.tags.add(self.tag_breakfast)
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing_sugar, amount=10
        )

    def test_get_recipes_list_anonymous_success(self):
        """Неавторизованный пользователь может просматривать рецепты."""
        response = self.client_anon.get('/api/recipes/')
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == 'Сладкий чай'

    def test_filter_recipes_by_tags(self):
        """Проверка работы фильтрации рецептов по слагам тегов."""
        other_recipe = Recipe.objects.create(
            author=self.author, name='Суп', text='Варить', cooking_time=20
        )
        other_recipe.tags.add(self.tag_lunch)

        response = self.client_anon.get(
            '/api/recipes/', {'tags': 'breakfast'}
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == 'Сладкий чай'

    def test_create_recipe_authenticated(self):
        """Авторизованный пользователь может успешно опубликовать свой рецепт."""
        payload = {
            'ingredients': [{'id': self.ing_sugar.id, 'amount': 15}],
            'tags': [self.tag_breakfast.id],
            'name': 'Новое блюдо',
            'image': (
                'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB'+
                'CAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
            ),
            'text': 'Описание нового блюда',
            'cooking_time': 10
        }
        response = self.client_auth.post(
            '/api/recipes/', data=payload, format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Recipe.objects.filter(name='Новое блюдо').exists()


    def test_add_to_favorite_success(self):
        """Авторизованный пользователь может добавить рецепт в избранное."""
        url = f'/api/recipes/{self.recipe.id}/favorite/'
        response = self.client_auth.post(url)

        assert response.status_code == status.HTTP_201_CREATED
        assert Favorite.objects.filter(
            user=self.user, recipe=self.recipe
        ).exists()
        assert response.data['id'] == self.recipe.id

    def test_remove_from_favorite_success(self):
        """Пользователь может успешно удалить рецепт из избранного."""
        Favorite.objects.create(user=self.user, recipe=self.recipe)
        url = f'/api/recipes/{self.recipe.id}/favorite/'

        response = self.client_auth.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Favorite.objects.filter(
            user=self.user, recipe=self.recipe
        ).exists()

    def test_add_to_shopping_cart_success(self):
        """Пользователь может добавить рецепт в список покупок."""
        url = f'/api/recipes/{self.recipe.id}/shopping_cart/'
        response = self.client_auth.post(url)

        assert response.status_code == status.HTTP_201_CREATED
        assert ShoppingCart.objects.filter(
            user=self.user, recipe=self.recipe
        ).exists()

    def test_anonymous_cannot_add_to_favorite(self):
        """Неавторизованный пользователь получает 401 в закрытых эндпоинтах."""
        url = f'/api/recipes/{self.recipe.id}/favorite/'
        response = self.client_anon.post(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
