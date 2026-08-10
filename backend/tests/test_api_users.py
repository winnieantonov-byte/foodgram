import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.users.models import Subscription

User = get_user_model()


@pytest.mark.django_db
class TestUserAndAuthAPI:
    """Тесты эндпоинтов регистрации, аутентификации и профилей."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.client = APIClient()
        self.register_url = '/api/users/'
        self.login_url = '/api/auth/token/login/'
        self.me_url = '/api/users/me/'

    def test_registration_valid_data(self):
        """Гость может успешно зарегистрироваться (Contract/PEP8)."""
        payload = {
            'username': 'new_chef',
            'email': 'new_chef@foodgram.com',
            'first_name': 'Алексей',
            'last_name': 'Петров',
            'password': 'very_secret_pass_123'
        }
        response = self.client.post(
            self.register_url, data=payload, format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['username'] == payload['username']
        assert response.data['email'] == payload['email']
        assert 'id' in response.data
        assert 'password' not in response.data

    def test_anonymous_user_me_endpoint_returns_401(self):
        """Неавторизованный пользователь не имеет доступа к /me/."""
        response = self.client.get(self.me_url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestSubscriptionsAPI:
    """Интеграционные тесты для системы подписок (Follow System)."""

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client_user = APIClient()
        self.user = User.objects.create_user(
            username='follower_user',
            email='follower@test.com',
            password='password123'
        )
        self.author = User.objects.create_user(
            username='star_chef',
            email='chef@test.com',
            password='password123'
        )

        self.token = Token.objects.create(user=self.user)
        self.client_user.credentials(
            HTTP_AUTHORIZATION=f'Token {self.token.key}'
        )

    def test_subscribe_to_author_success(self):
        """Авторизованный пользователь может подписаться на автора."""
        url = f'/api/users/{self.author.id}/subscribe/'
        response = self.client_user.post(url)

        assert response.status_code == status.HTTP_201_CREATED
        assert Subscription.objects.filter(
            user=self.user, author=self.author
        ).exists()
        assert response.data['email'] == self.author.email
        assert 'recipes' in response.data

    def test_cannot_subscribe_twice(self):
        """DRY/Бизнес-логика: Нельзя повторно подписаться на автора."""
        Subscription.objects.create(user=self.user, author=self.author)
        url = f'/api/users/{self.author.id}/subscribe/'

        response = self.client_user.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_subscribe_to_oneself(self):
        """Бизнес-логика: Запрет подписки на самого себя через API."""
        url = f'/api/users/{self.user.id}/subscribe/'
        response = self.client_user.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unsubscribe_success(self):
        """Пользователь может успешно отписаться от автора."""
        Subscription.objects.create(user=self.user, author=self.author)
        url = f'/api/users/{self.author.id}/subscribe/'

        response = self.client_user.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Subscription.objects.filter(
            user=self.user, author=self.author
        ).exists()

    def test_subscriptions_list_endpoint(self):
        """Проверка эндпоинта 'Мои подписки' с учетом пагинации."""
        Subscription.objects.create(user=self.user, author=self.author)
        url = '/api/users/subscriptions/'

        response = self.client_user.get(url)
        assert response.status_code == status.HTTP_200_OK

        # Проверяем структуру пагинированного ответа (results)
        assert 'results' in response.data
        assert len(response.data['results']) == 1

        # Извлекаем автора из списка результатов для проверки контракта
        author_data = response.data['results'][0]
        assert author_data['id'] == self.author.id
        assert author_data['username'] == self.author.username
