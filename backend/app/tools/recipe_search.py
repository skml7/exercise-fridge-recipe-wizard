from __future__ import annotations

from typing import List, Optional

import requests

from ..config import settings
from ..models import FridgeInput, RecipeOption


def _to_csv(values: List[str]) -> str:
    return ",".join([v.strip() for v in values if v.strip()])


def _mealdb_get(path: str, params: dict) -> dict | None:
    api_key = settings.mealdb_api_key or "1"
    url = f"https://www.themealdb.com/api/json/v1/{api_key}/{path}"
    try:
        response = requests.get(url, params=params, timeout=10)
    except Exception:
        return None
    if response.status_code != 200:
        return None
    return response.json()


def _mealdb_extract_ingredients(meal: dict) -> List[str]:
    ingredients: List[str] = []
    for i in range(1, 21):
        ing = (meal.get(f"strIngredient{i}") or "").strip()
        meas = (meal.get(f"strMeasure{i}") or "").strip()
        if ing:
            ingredients.append(f"{meas} {ing}".strip())
    return ingredients


def _spoonacular_search(fridge_input: FridgeInput) -> List[RecipeOption]:
    if not settings.spoonacular_api_key:
        return []

    ingredients = fridge_input.main_vegetables + fridge_input.aromatics + fridge_input.spices
    if fridge_input.proteins:
        ingredients += fridge_input.proteins

    params = {
        "apiKey": settings.spoonacular_api_key,
        "includeIngredients": _to_csv(ingredients),
        "cuisine": fridge_input.cuisine_mood,
        "number": 5,
        "instructionsRequired": True,
        "addRecipeInformation": True,
    }

    response = requests.get(
        "https://api.spoonacular.com/recipes/complexSearch",
        params=params,
        timeout=10,
    )
    if response.status_code != 200:
        return []

    data = response.json()
    results = []
    for item in data.get("results", []):
        instructions = item.get("analyzedInstructions") or []
        steps = []
        if instructions:
            steps = [step.get("step", "") for step in instructions[0].get("steps", [])]
        results.append(
            RecipeOption(
                title=item.get("title", "Recipe option"),
                cuisine=fridge_input.cuisine_mood,
                time_minutes=item.get("readyInMinutes", fridge_input.time_budget_minutes),
                difficulty="easy",
                ingredients=[i.get("original", "") for i in item.get("extendedIngredients", [])],
                steps=[s for s in steps if s],
                notes="Sourced from Spoonacular.",
                source="spoonacular",
                source_url=item.get("sourceUrl"),
            )
        )
    return results


def _mealdb_search(fridge_input: FridgeInput) -> List[RecipeOption]:
    # TheMealDB's free key "1" is intended for development/testing.
    # The API supports filtering by a single ingredient; we pick the most salient ingredient.
    seed_ingredient = (
        (fridge_input.proteins[0] if fridge_input.proteins else None)
        or (fridge_input.main_vegetables[0] if fridge_input.main_vegetables else None)
        or None
    )
    if not seed_ingredient:
        return []

    filtered = _mealdb_get("filter.php", {"i": seed_ingredient})
    meals = (filtered or {}).get("meals") or []
    if not meals:
        return []

    results: List[RecipeOption] = []
    for item in meals[:5]:
        meal_id = item.get("idMeal")
        if not meal_id:
            continue
        detail = _mealdb_get("lookup.php", {"i": meal_id})
        meal = ((detail or {}).get("meals") or [None])[0]
        if not meal:
            continue

        instructions = (meal.get("strInstructions") or "").strip()
        steps = [s.strip() for s in instructions.split("\n") if s.strip()] or ["Follow the recipe instructions."]
        results.append(
            RecipeOption(
                title=meal.get("strMeal") or "Meal option",
                cuisine=meal.get("strArea") or fridge_input.cuisine_mood,
                time_minutes=fridge_input.time_budget_minutes,
                difficulty="easy",
                ingredients=_mealdb_extract_ingredients(meal),
                steps=steps,
                notes="Sourced from TheMealDB.",
                source="mealdb",
                source_url=f"https://www.themealdb.com/meal/{meal_id}",
            )
        )
    return results


def search_recipes(fridge_input: FridgeInput) -> List[RecipeOption]:
    if not settings.recipe_source_enabled:
        return []

    provider = settings.recipe_source_provider.lower().strip()
    if provider == "auto":
        # Prefer Spoonacular when a key exists; top up with TheMealDB if needed.
        options: List[RecipeOption] = []
        if settings.spoonacular_api_key:
            options.extend(_spoonacular_search(fridge_input))
        if len(options) < 5:
            existing = {o.title.strip().lower() for o in options}
            for o in _mealdb_search(fridge_input):
                if o.title.strip().lower() not in existing:
                    options.append(o)
                if len(options) >= 5:
                    break
        return options
    if provider == "spoonacular":
        return _spoonacular_search(fridge_input)
    if provider == "mealdb":
        return _mealdb_search(fridge_input)
    return []
