FROM python:3.10-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Запрещаем Python писать файлы кэша .pyc на диск
ENV PYTHONDONTWRITEBYTECODE 1
# Запрещаем Python буферизировать потоки stdout и stderr
ENV PYTHONUNBUFFERED 1

ENV PYTHONPATH=/app

# Устанавливаем системные зависимости для компиляции некоторых пакетов (например, psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Сначала копируем зависимости для оптимального кэширования Docker-слоев (DRY/Speed)
COPY requirements.txt .

# Устанавливаем зависимости бэкенда
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной код бэкенда в контейнер
COPY . .

# Собираем статические файлы при старте, запускаем миграции и поднимаем WSGI-сервер gunicorn
CMD ["python", "-m", "gunicorn.app.wsgiapp", "foodgram.wsgi:application", "--bind", "0.0.0.0:8000"]