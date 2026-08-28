from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.views import (
    CustomUserViewSet,
    IngredientViewSet,
    RecipeViewSet,
    TagViewSet,
)

app_name = 'api'

# Регистрация всех вьюсетов в роутере
router_v1 = DefaultRouter()
router_v1.register('users', CustomUserViewSet, basename='users')
router_v1.register('tags', TagViewSet, basename='tags')
router_v1.register('ingredients', IngredientViewSet, basename='ingredients')
router_v1.register('recipes', RecipeViewSet, basename='recipes')

urlpatterns = [
    # API маршруты
    path('', include(router_v1.urls)),

    # Аутентификация через токены (djoser)
    path('auth/', include('djoser.urls.authtoken')),

    # Короткие ссылки на рецепты
    path(
        's/<int:recipe_id>/', RecipeViewSet.as_view(
            {'get': 'redirect_short_link'}
        ), name='short-link'
    ),
]
