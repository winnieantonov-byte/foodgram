from django.http import HttpResponseRedirect

from apps.recipes.models import Recipe


def redirect_short_link(request, recipe_id: int) -> HttpResponseRedirect:
    """
    Перенаправляет по короткой ссылке на фронтовую страницу рецепта.
    Если рецепт не существует, перенаправляет на страницу 404.
    """
    recipe = Recipe.objects.filter(id=recipe_id).first()
    if recipe is None:
        return HttpResponseRedirect('/404/')
    return HttpResponseRedirect(f"/recipes/{recipe.id}/")
