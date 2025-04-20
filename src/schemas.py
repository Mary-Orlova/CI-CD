from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Union


class IngredientBase(BaseModel):
    title: str = Field(..., max_length=100, example="Томаты")

class IngredientIn(IngredientBase):
    quantity: str = Field(..., example="500 г")

class IngredientOut(IngredientBase):
    id: int

class RecipeBase(BaseModel):
    title: str = Field(..., max_length=100, example="Томатный суп")
    cook_time: int = Field(..., gt=0, example=40)

class RecipeCreate(RecipeBase):
    description: str = Field(..., max_length=1000, example="Обычный томатный суп")
    ingredients: List[IngredientIn] = Field(..., min_items=1)

class RecipeUpdate(BaseModel):
    title: Union[str, None] = Field(None, max_length=100)
    cook_time: Union[int, None] = Field(None, gt=0)
    description: Union[str, None] = Field(None, max_length=1000)
    ingredients: Union[List[IngredientIn], None] = Field(None, min_items=1)

class RecipeOut(RecipeBase):
    id: int
    description: str
    views: int
    ingredients: List[dict]

    class Config:
        orm_mode = True
