import pytest
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError

from apps.users.models import Subscription

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    """Тестирование кастомной модели пользователя."""

    def test_create_user(self):
        """Проверка успешного создания пользователя и метода __str__."""
        user = User.objects.create_user(
            username='test_chef',
            email='chef@foodgram.com',
            first_name='Алексей',
            last_name='Иванов',
            password='securepassword123'
        )
        assert User.objects.count() == 1
        assert str(user) == 'test_chef'
        assert user.email == 'chef@foodgram.com'
        assert user.get_full_name() == 'Алексей Иванов'


@pytest.mark.django_db
class TestSubscriptionModel:
    """Тестирование модели подписок на авторов (Follow System)."""

    @pytest.fixture
    def setup_users(self):
        """Фикстура для создания двух разных пользователей."""
        follower = User.objects.create_user(
            username='follower',
            email='follower@test.com',
            password='password123'
        )
        author = User.objects.create_user(
            username='author',
            email='author@test.com',
            password='password123'
        )
        return follower, author

    def test_subscription_creation(self, setup_users):
        """Проверка корректности создания связи подписки."""
        follower, author = setup_users
        subscription = Subscription.objects.create(
            user=follower,
            author=author
        )
        assert Subscription.objects.count() == 1
        assert str(subscription) == 'follower подписан на author'

    def test_unique_subscription_constraint(self, setup_users):
        """Бизнес-логика: нельзя дважды подписаться на одного автора."""
        follower, author = setup_users
        Subscription.objects.create(user=follower, author=author)

        # Повторная попытка должна упасть на уровне СУБД (UniqueConstraint)
        with pytest.raises(IntegrityError):
            Subscription.objects.create(user=follower, author=author)

    def test_self_subscription_constraint(self, setup_users):
        """Бизнес-логика: пользователь не может подписаться сам на себя."""
        follower, _ = setup_users

        # Попытка самоподписки падает из-за CheckConstraint базы данных
        with pytest.raises(IntegrityError):
            Subscription.objects.create(user=follower, author=follower)
