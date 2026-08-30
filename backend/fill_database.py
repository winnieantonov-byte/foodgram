import base64
import json
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from apps.recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
)
from apps.users.models import Subscription

User = get_user_model()

# ============================================================
# УДАЛЕНИЕ БАЗЫ ДАННЫХ И ВЫПОЛНЕНИЕ МИГРАЦИЙ
# ============================================================

if os.path.exists('db.sqlite3'):
    os.remove('db.sqlite3')
    print("🗑️  База данных удалена")

print("🔄 Выполняем миграции...")
subprocess.run([sys.executable, 'manage.py', 'makemigrations'], check=True)
subprocess.run([sys.executable, 'manage.py', 'migrate'], check=True)
print("✅ Миграции выполнены")

# ============================================================
# ЗАГРУЗКА ИНГРЕДИЕНТОВ ИЗ JSON
# ============================================================

DATA_DIR = settings.BASE_DIR / 'data'
INGREDIENTS_FILE = DATA_DIR / 'ingredients.json'


def load_ingredients_from_json():
    """Загружает ингредиенты из JSON файла."""
    print("\n" + "=" * 60)
    print("3. ЗАГРУЗКА ИНГРЕДИЕНТОВ ИЗ JSON")
    print("=" * 60)

    if not INGREDIENTS_FILE.exists():
        print(f"  ❌ Файл не найден: {INGREDIENTS_FILE}")
        return {}

    with open(INGREDIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    ingredients = {}
    ingredients_to_create = []

    for item in data:
        if isinstance(item, dict):
            name = item.get('name', '').strip()
            unit = item.get('measurement_unit', '').strip()
            if name and unit:
                ingredients_to_create.append(
                    Ingredient(name=name, measurement_unit=unit)
                )

    # Создаем все ингредиенты одним запросом в БД
    Ingredient.objects.bulk_create(
        ingredients_to_create,
        ignore_conflicts=True,
        batch_size=1000,
    )

    # Собираем словарь для дальнейшего использования
    for ing in Ingredient.objects.filter(
        name__in=[ing.name for ing in ingredients_to_create]
    ):
        ingredients[ing.name] = ing

    print(f"  📊 Всего ингредиентов из JSON: {len(ingredients)}")
    return ingredients


def create_users():
    """Создает пользователей."""
    print("=" * 60)
    print("1. СОЗДАНИЕ ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 60)

    users_data = [
        {
            'username': 'user1',
            'email': 'user1@example.com',
            'first_name': 'Иван',
            'last_name': 'Иванов',
            'password': 'password123'
        },
        {
            'username': 'user2',
            'email': 'user2@example.com',
            'first_name': 'Петр',
            'last_name': 'Петров',
            'password': 'password123'
        },
        {
            'username': 'user3',
            'email': 'user3@example.com',
            'first_name': 'Сергей',
            'last_name': 'Сергеев',
            'password': 'password123'
        },
        {
            'username': 'user4',
            'email': 'user4@example.com',
            'first_name': 'Анна',
            'last_name': 'Смирнова',
            'password': 'password123'
        },
        {
            'username': 'user5',
            'email': 'user5@example.com',
            'first_name': 'Мария',
            'last_name': 'Козлова',
            'password': 'password123'
        },
    ]

    users = {}
    for user_data in users_data:
        user, created = User.objects.get_or_create(
            username=user_data['username'],
            defaults={
                'email': user_data['email'],
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name'],
            }
        )
        if created:
            user.set_password(user_data['password'])
            user.save()
            print(
                f"  ✅ Создан пользователь: {user.username} (ID: {user.id})"
            )
        else:
            print(
                f"  ℹ️ Пользователь уже сущ.: {user.username} (ID: {user.id})"
            )
        users[user.username] = user

    return users


def create_tags():
    """Создает теги."""
    print("\n" + "=" * 60)
    print("2. СОЗДАНИЕ ТЕГОВ")
    print("=" * 60)

    tags_data = [
        {'name': 'Завтрак', 'slug': 'breakfast'},
        {'name': 'Обед', 'slug': 'lunch'},
        {'name': 'Ужин', 'slug': 'dinner'},
        {'name': 'Десерт', 'slug': 'dessert'},
        {'name': 'Салаты', 'slug': 'salads'},
        {'name': 'Супы', 'slug': 'soups'},
        {'name': 'Выпечка', 'slug': 'baking'},
        {'name': 'Напитки', 'slug': 'drinks'},
        {'name': 'Закуски', 'slug': 'snacks'},
        {'name': 'Веганское', 'slug': 'vegan'},
    ]

    tags = {}
    for tag_data in tags_data:
        tag, created = Tag.objects.get_or_create(
            slug=tag_data['slug'],
            defaults={'name': tag_data['name']}
        )
        if created:
            print(
                f"  ✅ Создан тег: {tag.name} (slug: {tag.slug}, ID: {tag.id})"
            )
        else:
            print(
                f"  ℹ️ Тег уже сущ. : {tag.name}(slug:{tag.slug},ID:{tag.id})"
            )
        tags[tag.slug] = tag

    return tags


def create_recipes(users, tags, ingredients):
    """Создает рецепты."""
    print("\n" + "=" * 60)
    print("4. СОЗДАНИЕ РЕЦЕПТОВ")
    print("=" * 60)

    dummy_image = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )

    recipes_data = [
        # Рецепты от user1
        {
            'author': 'user1',
            'name': 'Блины классические',
            'text': (
                'Классический рецепт русских блинов. Смешайте муку, '
                'сахар, соль, яйца и молоко. Взбейте до однородности. '
                'Жарьте на разогретой сковороде.'
            ),
            'cooking_time': 30,
            'tags': ['breakfast', 'baking'],
            'ingredients': [
                {'name': 'мука', 'amount': 200},
                {'name': 'сахар', 'amount': 50},
                {'name': 'молоко', 'amount': 500},
                {'name': 'яйца куриные', 'amount': 3},
                {'name': 'соль', 'amount': 5},
                {'name': 'растительное масло', 'amount': 30},
            ]
        },
        {
            'author': 'user1',
            'name': 'Салат Оливье',
            'text': (
                'Любимый новогодний салат. Нарежьте все ингредиенты '
                'и смешайте с майонезом.'
            ),
            'cooking_time': 45,
            'tags': ['salads', 'snacks'],
            'ingredients': [
                {'name': 'картофель', 'amount': 4},
                {'name': 'морковь', 'amount': 2},
                {'name': 'яйца куриные', 'amount': 4},
                {'name': 'огурцы', 'amount': 3},
                {'name': 'колбаса', 'amount': 300},
                {'name': 'горошек зеленый', 'amount': 100},
                {'name': 'майонез', 'amount': 200},
                {'name': 'соль', 'amount': 5},
            ]
        },
        {
            'author': 'user1',
            'name': 'Шоколадный торт',
            'text': (
                'Праздничный шоколадный торт. Смешайте все ингредиенты '
                'и выпекайте в духовке.'
            ),
            'cooking_time': 120,
            'tags': ['dessert', 'baking'],
            'ingredients': [
                {'name': 'мука', 'amount': 200},
                {'name': 'сахар', 'amount': 200},
                {'name': 'яйца куриные', 'amount': 4},
                {'name': 'какао-порошок', 'amount': 50},
                {'name': 'сливочное масло', 'amount': 200},
                {'name': 'молоко', 'amount': 100},
                {'name': 'разрыхлитель', 'amount': 10},
            ]
        },
        {
            'author': 'user1',
            'name': 'Овощной салат',
            'text': (
                'Свежий салат из овощей. Нарежьте помидоры и огурцы, '
                'добавьте масло и соль.'
            ),
            'cooking_time': 15,
            'tags': ['salads', 'vegan'],
            'ingredients': [
                {'name': 'помидоры', 'amount': 2},
                {'name': 'огурцы', 'amount': 2},
                {'name': 'растительное масло', 'amount': 2},
                {'name': 'соль', 'amount': 3},
                {'name': 'зелень', 'amount': 20},
            ]
        },
        {
            'author': 'user1',
            'name': 'Куриный суп',
            'text': (
                'Легкий домашний суп с курицей. Сварите бульон, '
                'добавьте овощи и лапшу.'
            ),
            'cooking_time': 60,
            'tags': ['soups', 'dinner'],
            'ingredients': [
                {'name': 'курица', 'amount': 400},
                {'name': 'лук репчатый', 'amount': 1},
                {'name': 'морковь', 'amount': 1},
                {'name': 'картофель', 'amount': 2},
                {'name': 'вода', 'amount': 2000},
                {'name': 'соль', 'amount': 8},
                {'name': 'зелень', 'amount': 20},
            ]
        },
        {
            'author': 'user1',
            'name': 'Плов',
            'text': 'Вкусный узбекский плов с мясом и рисом.',
            'cooking_time': 90,
            'tags': ['lunch', 'dinner'],
            'ingredients': [
                {'name': 'рис', 'amount': 300},
                {'name': 'мясо', 'amount': 500},
                {'name': 'лук репчатый', 'amount': 2},
                {'name': 'морковь', 'amount': 2},
                {'name': 'растительное масло', 'amount': 100},
                {'name': 'соль', 'amount': 10},
                {'name': 'вода', 'amount': 500},
            ]
        },
        {
            'author': 'user2',
            'name': 'Борщ украинский',
            'text': (
                'Наваристый красный борщ со сметаной. Сварите бульон '
                'из говядины, добавьте овощи.'
            ),
            'cooking_time': 90,
            'tags': ['soups', 'dinner'],
            'ingredients': [
                {'name': 'говядина', 'amount': 500},
                {'name': 'картофель', 'amount': 3},
                {'name': 'лук репчатый', 'amount': 1},
                {'name': 'морковь', 'amount': 1},
                {'name': 'свекла', 'amount': 2},
                {'name': 'чеснок', 'amount': 3},
                {'name': 'соль', 'amount': 10},
                {'name': 'сметана', 'amount': 100},
            ]
        },
        {
            'author': 'user2',
            'name': 'Омлет',
            'text': (
                'Нежный омлет с овощами. Взбейте яйца, добавьте молоко '
                'и жарьте.'
            ),
            'cooking_time': 20,
            'tags': ['breakfast'],
            'ingredients': [
                {'name': 'яйца куриные', 'amount': 3},
                {'name': 'молоко', 'amount': 100},
                {'name': 'растительное масло', 'amount': 20},
                {'name': 'соль', 'amount': 3},
                {'name': 'помидоры', 'amount': 1},
            ]
        },
        {
            'author': 'user2',
            'name': 'Греческий салат',
            'text': (
                'Классический греческий салат с оливками и сыром.'
            ),
            'cooking_time': 15,
            'tags': ['salads', 'vegan'],
            'ingredients': [
                {'name': 'помидоры', 'amount': 3},
                {'name': 'огурцы', 'amount': 2},
                {'name': 'оливки', 'amount': 50},
                {'name': 'сыр', 'amount': 100},
                {'name': 'растительное масло', 'amount': 30},
                {'name': 'соль', 'amount': 3},
            ]
        },
        {
            'author': 'user2',
            'name': 'Творожная запеканка',
            'text': 'Нежная запеканка для детского завтрака.',
            'cooking_time': 50,
            'tags': ['breakfast', 'dessert'],
            'ingredients': [
                {'name': 'творог', 'amount': 500},
                {'name': 'яйца куриные', 'amount': 3},
                {'name': 'сахар', 'amount': 100},
                {'name': 'сметана', 'amount': 100},
                {'name': 'ванилин', 'amount': 5},
            ]
        },
        {
            'author': 'user2',
            'name': 'Жареные овощи',
            'text': (
                'Ароматные овощи на масле. Обжарьте овощи с чесноком.'
            ),
            'cooking_time': 25,
            'tags': ['dinner', 'vegan'],
            'ingredients': [
                {'name': 'помидоры', 'amount': 2},
                {'name': 'растительное масло', 'amount': 30},
                {'name': 'чеснок', 'amount': 2},
                {'name': 'соль', 'amount': 5},
                {'name': 'зелень', 'amount': 20},
            ]
        },
        {
            'author': 'user3',
            'name': 'Салат Цезарь',
            'text': (
                'Классический салат Цезарь с курицей и сухариками.'
            ),
            'cooking_time': 30,
            'tags': ['salads', 'lunch'],
            'ingredients': [
                {'name': 'курица', 'amount': 300},
                {'name': 'салат', 'amount': 200},
                {'name': 'сыр', 'amount': 50},
                {'name': 'майонез', 'amount': 100},
                {'name': 'чеснок', 'amount': 1},
                {'name': 'лимоны', 'amount': 1},
            ]
        },
        {
            'author': 'user3',
            'name': 'Овсянка с фруктами',
            'text': (
                'Полезный завтрак с овсянкой и свежими фруктами.'
            ),
            'cooking_time': 15,
            'tags': ['breakfast', 'vegan'],
            'ingredients': [
                {'name': 'овсяные хлопья', 'amount': 100},
                {'name': 'молоко', 'amount': 200},
                {'name': 'бананы', 'amount': 1},
                {'name': 'яблоки', 'amount': 1},
                {'name': 'мед', 'amount': 20},
            ]
        },
        {
            'author': 'user3',
            'name': 'Паста с курицей',
            'text': (
                'Итальянская паста с курицей и сливочным соусом.'
            ),
            'cooking_time': 40,
            'tags': ['lunch', 'dinner'],
            'ingredients': [
                {'name': 'курица', 'amount': 300},
                {'name': 'сливки', 'amount': 200},
                {'name': 'растительное масло', 'amount': 30},
                {'name': 'чеснок', 'amount': 2},
                {'name': 'соль', 'amount': 5},
                {'name': 'сыр', 'amount': 50},
            ]
        },
        {
            'author': 'user3',
            'name': 'Фруктовый салат',
            'text': 'Свежий фруктовый салат с йогуртом.',
            'cooking_time': 10,
            'tags': ['dessert', 'vegan'],
            'ingredients': [
                {'name': 'яблоки', 'amount': 2},
                {'name': 'бананы', 'amount': 2},
                {'name': 'апельсины', 'amount': 1},
                {'name': 'клубника', 'amount': 100},
                {'name': 'йогурт', 'amount': 100},
                {'name': 'мед', 'amount': 20},
            ]
        },
        {
            'author': 'user3',
            'name': 'Уха',
            'text': 'Рыбный суп с картофелем и зеленью.',
            'cooking_time': 50,
            'tags': ['soups', 'dinner'],
            'ingredients': [
                {'name': 'рыба', 'amount': 500},
                {'name': 'картофель', 'amount': 3},
                {'name': 'лук репчатый', 'amount': 1},
                {'name': 'морковь', 'amount': 1},
                {'name': 'вода', 'amount': 2000},
                {'name': 'соль', 'amount': 8},
                {'name': 'зелень', 'amount': 20},
            ]
        },
    ]

    recipes = []
    for recipe_data in recipes_data:
        author = users[recipe_data['author']]

        recipe = Recipe.objects.create(
            author=author,
            name=recipe_data['name'],
            text=recipe_data['text'],
            cooking_time=recipe_data['cooking_time'],
        )

        format, imgstr = dummy_image.split(';base64,')
        ext = format.split('/')[-1]
        recipe.image.save(
            f'recipe_{recipe.id}.{ext}',
            ContentFile(base64.b64decode(imgstr)),
            save=True
        )

        recipe.tags.set([tags[tag_slug] for tag_slug in recipe_data['tags']])

        for ing_data in recipe_data['ingredients']:
            ingredient = ingredients[ing_data['name']]
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient=ingredient,
                amount=ing_data['amount']
            )

        recipes.append(recipe)
        print(
            f"  ✅ Создан рецепт {recipe.id}: {recipe.name} "
            f"(автор: {recipe.author.username})"
        )

    return recipes


def create_subscriptions(users):
    """Создает подписки."""
    print("\n" + "=" * 60)
    print("5. СОЗДАНИЕ ПОДПИСОК")
    print("=" * 60)

    subscriptions_data = [
        {'user': 'user1', 'author': 'user2'},
        {'user': 'user1', 'author': 'user3'},
        {'user': 'user1', 'author': 'user4'},
        {'user': 'user2', 'author': 'user1'},
        {'user': 'user2', 'author': 'user3'},
        {'user': 'user3', 'author': 'user1'},
        {'user': 'user3', 'author': 'user2'},
        {'user': 'user4', 'author': 'user1'},
        {'user': 'user4', 'author': 'user2'},
        {'user': 'user5', 'author': 'user1'},
    ]

    for sub_data in subscriptions_data:
        user = users[sub_data['user']]
        author = users[sub_data['author']]
        sub, created = Subscription.objects.get_or_create(
            user=user,
            author=author
        )
        if created:
            print(f"  ✅ {sub_data['user']} подписан на {sub_data['author']}")
        else:
            print(
                f"  ℹ️ Подписка уже существует: "
                f"{sub_data['user']} -> {sub_data['author']}"
            )


def create_favorites(users, recipes):
    """Добавляет рецепты в избранное."""
    print("\n" + "=" * 60)
    print("6. ДОБАВЛЕНИЕ В ИЗБРАННОЕ")
    print("=" * 60)

    favorites_data = [
        {'user': 'user1', 'recipe': 0},
        {'user': 'user1', 'recipe': 1},
        {'user': 'user2', 'recipe': 2},
        {'user': 'user2', 'recipe': 3},
        {'user': 'user3', 'recipe': 4},
        {'user': 'user3', 'recipe': 5},
        {'user': 'user4', 'recipe': 6},
        {'user': 'user5', 'recipe': 7},
    ]

    for fav_data in favorites_data:
        user = users[fav_data['user']]
        recipe = recipes[fav_data['recipe']]
        fav, created = Favorite.objects.get_or_create(
            user=user,
            recipe=recipe
        )
        if created:
            print(f"  ✅ {fav_data['user']} добавил в избранное: {recipe.name}")
        else:
            print(
                f"  ℹ️ Уже в избранном: "
                f"{fav_data['user']} -> {recipe.name}"
            )


def create_shopping_cart(users, recipes):
    """Добавляет рецепты в корзину."""
    print("\n" + "=" * 60)
    print("7. ДОБАВЛЕНИЕ В КОРЗИНУ")
    print("=" * 60)

    cart_data = [
        {'user': 'user1', 'recipe': 0},
        {'user': 'user1', 'recipe': 1},
        {'user': 'user2', 'recipe': 2},
        {'user': 'user2', 'recipe': 3},
        {'user': 'user3', 'recipe': 4},
        {'user': 'user3', 'recipe': 5},
        {'user': 'user4', 'recipe': 6},
        {'user': 'user5', 'recipe': 7},
    ]

    for cart in cart_data:
        user = users[cart['user']]
        recipe = recipes[cart['recipe']]
        cart_obj, created = ShoppingCart.objects.get_or_create(
            user=user,
            recipe=recipe
        )
        if created:
            print(f"  ✅ {cart['user']} добавил в корзину: {recipe.name}")
        else:
            print(
                f"  ℹ️ Уже в корзине: "
                f"{cart['user']} -> {recipe.name}"
            )


def main():
    """Главная функция."""
    print("=" * 60)
    print("🚀 НАЧАЛО СОЗДАНИЯ ТЕСТОВЫХ ДАННЫХ")
    print("=" * 60)

    users = create_users()
    tags = create_tags()
    ingredients = load_ingredients_from_json()
    recipes = create_recipes(users, tags, ingredients)
    create_subscriptions(users)
    create_favorites(users, recipes)
    create_shopping_cart(users, recipes)

    print("\n" + "=" * 60)
    print("📊 ИТОГИ СОЗДАНИЯ ТЕСТОВЫХ ДАННЫХ:")
    print("=" * 60)
    print(f"  👤 Пользователей: {User.objects.count()}")
    print(f"  🏷️ Тегов: {Tag.objects.count()}")
    print(f"  🥕 Ингредиентов: {Ingredient.objects.count()}")
    print(f"  📖 Рецептов: {Recipe.objects.count()}")
    print(f"  🔄 Подписок: {Subscription.objects.count()}")
    print(f"  ⭐ В избранном: {Favorite.objects.count()}")
    print(f"  🛒 В корзине: {ShoppingCart.objects.count()}")
    print("=" * 60)
    print("✅ ВСЕ ДАННЫЕ УСПЕШНО СОЗДАНЫ!")
    print("=" * 60)


main()
