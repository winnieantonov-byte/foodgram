from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


class User(AbstractUser):
    """Кастомная модель пользователя для проекта Foodgram."""

    # Переопределяем email
    # делая его уникальным и обязательным (требование API)
    email = models.EmailField(
        'Адрес электронной почты',
        max_length=254,
        unique=True,
    )
    first_name = models.CharField(
        'Имя',
        max_length=150,
    )
    last_name = models.CharField(
        'Фамилия',
        max_length=150,
    )
    # Валидатор для юзернейма
    # исключающий системные имена и странные символы
    username = models.CharField(
        'Уникальный юзернейм',
        max_length=150,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[\w.@+-]+\Z',
                message='Юзернейм содержит недопустимые символы.'
            )
        ]
    )
    avatar = models.ImageField(
        'Аватар профиля',
        upload_to='users/avatars/',
        blank=True,
        null=True,
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        ordering = ['id']
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self) -> str:
        return self.username


class Subscription(models.Model):
    """Модель подписки пользователей на авторов рецептов."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='follower',
        verbose_name='Подписчик',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='following',
        verbose_name='Автор',
    )

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        constraints = [
            # Защита на уровне БД: уникальность пары подписчик-автор
            models.UniqueConstraint(
                fields=['user', 'author'],
                name='unique_user_author_subscription'
            ),
            # Защита на уровне БД: запрет подписки на самого себя
            models.CheckConstraint(
                check=~models.Q(user=models.F('author')),
                name='prevent_self_subscription'
            )
        ]

    def __str__(self) -> str:
        return f'{self.user} подписан на {self.author}'
