import os

from django.core.wsgi import get_wsgi_application

# Указываем путь к файлу настроек нашего проекта
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodgram.settings')

application = get_wsgi_application()
