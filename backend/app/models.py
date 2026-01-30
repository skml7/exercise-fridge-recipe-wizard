from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class FridgeInput(BaseModel):
    main_vegetables: List[str] = Field(default_factory=list)
    aromatics: List[str] = Field(default_factory=list)
    spices: List[str] = Field(default_factory=list)
    proteins: List[str] = Field(default_factory=list)
    dietary: List[str] = Field(default_factory=list)
    cuisine_mood: str = "quick and comforting"
    time_budget_minutes: int = 30
    servings: int = 2
    equipment: List[str] = Field(default_factory=list)


class RecipeOption(BaseModel):
    title: str
    cuisine: str
    time_minutes: int
    difficulty: str
    ingredients: List[str]
    steps: List[str]
    notes: Optional[str] = None
    source: str = "generated"
    source_url: Optional[str] = None


class RecipeChoiceRequest(BaseModel):
    option_id: str
    fridge_input: FridgeInput


class RecipeResponse(BaseModel):
    options: List[RecipeOption]
    selected: Optional[RecipeOption] = None
    shopping_list: List[str] = Field(default_factory=list)


class RagConfig(BaseModel):
    enabled: bool = False
    collection_name: str = "fridge-recipes"
    top_k: int = 4


class RecipeSourceConfig(BaseModel):
    provider: str = "spoonacular"  # spoonacular | mealdb | none
    enabled: bool = True
