import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings

from apps.recipes.models import Ingredient


class Command(BaseCommand):
    """Кастомная команда для импорта ингредиентов из JSON файла."""

    help = 'Загружает базовый список ингредиентов из папки data/'

    def handle(self, *args, **options) -> None:
        file_path = os.path.join(settings.BASE_DIR, 'data', 'ingredients.json')
        if not os.path.exists(file_path):
            self.stdout.write(
                self.style.ERROR(f'Файл не найден по пути: {file_path}')
            )
            return

        self.stdout.write('Начало импорта ингредиентов...')

        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        ingredients_to_create = []
        for item in data:
            ingredients_to_create.append(
                Ingredient(
                    name=item['name'],
                    measurement_unit=item['measurement_unit']
                )
            )

        Ingredient.objects.bulk_create(
            ingredients_to_create, ignore_conflicts=True
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно импортировано {len(data)} ингредиентов.'
            )
        )
