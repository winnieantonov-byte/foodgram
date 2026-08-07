import pytest
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError

from apps.users.models import Subscription

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    """Тестирование кастомной модели пользователя на соответствие PEP8 и DRY."""

    def test_create_user(self):
        """Проверка успешного создания пользователя с валидными данными."""
        user = User.objects.create_user(
            username='chef_ivan',
            email='ivan@foodgram.com',
            first_name='Иван',
            last_name='Иванов',
            password='secure_password123'
        )
        assert user.username == 'chef_ivan'
        assert user.email == 'ivan@foodgram.com'
        assert user.get_full_name() == 'Иван Иванов'
        assert str(user) == 'chef_ivan'


@pytest.mark.django_db
class TestSubscriptionModel:
    """Тестирование бизнес-логики подписок."""

    @pytest.fixture
    def setup_users(self):
        """Создание тестовых пользователей."""
        follower = User.objects.create_user(
            username='user_buyer', email='buyer@test.com'
        )
        author = User.objects.create_user(
            username='chef_pro', email='chef@test.com'
        )
        return follower, author

    def test_subscription_creation(self, setup_users):
        """Проверка создания связи подписки."""
        follower, author = setup_users
        subscription = Subscription.objects.create(
            user=follower, author=author
        )
        
        assert subscription.user == follower
        assert subscription.author == author
        assert str(subscription) == f'{follower} подписан на {author}'

    def test_unique_subscription_constraint(self, setup_users):
        """DRY/Integrity: Нельзя подписаться на одного автора дважды."""
        follower, author = setup_users
        Subscription.objects.create(user=follower, author=author)
        
        with pytest.raises(IntegrityError):
            Subscription.objects.create(user=follower, author=author)

    def test_self_subscription_constraint(self, setup_users):
        """Бизнес-логика: Пользователь не может подписаться на самого себя."""
        follower, _ = setup_users
        
        # Этот тест упадет на этапе написания кода, если мы не добавим CheckConstraint
        with pytest.raises(IntegrityError):
            Subscription.objects.create(user=follower, author=follower)
