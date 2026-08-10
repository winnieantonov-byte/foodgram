from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.views import (
    CustomUserViewSet, IngredientViewSet, RecipeViewSet, TagViewSet
)

app_name = 'api'

# Регистрируем все сущности в едином REST-роутере (DRY)
router_v1 = DefaultRouter()
router_v1.register('users', CustomUserViewSet, basename='users')
router_v1.register('tags', TagViewSet, basename='tags')
router_v1.register('ingredients', IngredientViewSet, basename='ingredients')
router_v1.register('recipes', RecipeViewSet, basename='recipes')

urlpatterns = [
    # Все роуты вьюсетов:
    # /api/users/, /api/recipes/, /api/tags/, etc.
    path('', include(router_v1.urls)),

    # Стандартные эндпоинты djoser для токенов:
    # /api/auth/token/login/ и logout/
    path('auth/', include('djoser.urls.authtoken')),
]
