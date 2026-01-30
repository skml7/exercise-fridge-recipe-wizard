from __future__ import annotations

from typing import List, Optional

import requests

from ..config import settings
from ..models import FridgeInput, RecipeOption


def _to_csv(values: List[str]) -> str:
    return ",".join([v.strip() for v in values if v.strip()])


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


def _edamam_search(fridge_input: FridgeInput) -> List[RecipeOption]:
    if not settings.edamam_app_id or not settings.edamam_app_key:
        return []

    ingredients = fridge_input.main_vegetables + fridge_input.aromatics + fridge_input.spices
    if fridge_input.proteins:
        ingredients += fridge_input.proteins

    params = {
        "type": "public",
        "app_id": settings.edamam_app_id,
        "app_key": settings.edamam_app_key,
        "q": _to_csv(ingredients) or "weeknight dinner",
        "cuisineType": fridge_input.cuisine_mood,
    }

    response = requests.get(
        "https://api.edamam.com/api/recipes/v2",
        params=params,
        timeout=10,
    )
    if response.status_code != 200:
        return []

    data = response.json()
    results = []
    for hit in data.get("hits", []):
        recipe = hit.get("recipe", {})
        results.append(
            RecipeOption(
                title=recipe.get("label", "Recipe option"),
                cuisine=", ".join(recipe.get("cuisineType", []) or [fridge_input.cuisine_mood]),
                time_minutes=int(recipe.get("totalTime", fridge_input.time_budget_minutes) or fridge_input.time_budget_minutes),
                difficulty="easy",
                ingredients=recipe.get("ingredientLines", []) or [],
                steps=["Follow instructions at the source."],
                notes="Sourced from Edamam.",
                source="edamam",
                source_url=recipe.get("url"),
            )
        )
    return results


def search_recipes(fridge_input: FridgeInput) -> List[RecipeOption]:
    if not settings.recipe_source_enabled:
        return []

    provider = settings.recipe_source_provider.lower().strip()
    if provider == "spoonacular":
        return _spoonacular_search(fridge_input)
    if provider == "edamam":
        return _edamam_search(fridge_input)
    return []
