from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredient"

    recipe_id = Column(Integer, ForeignKey('recipes.id'), primary_key=True)
    recipe = relationship("Recipe", back_populates="recipe_ingredients")
    ingredient_id = Column(Integer, ForeignKey('ingredients.id'), primary_key=True)
    quantity = Column(String(50))


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), unique=True, nullable=False)
    description = Column(String(1000))
    cook_time = Column(Integer, nullable=False)
    views = Column(Integer, default=0)

    ingredients = relationship(
        "Ingredient",
        secondary="recipe_ingredient",
        back_populates="recipes",
        lazy="select"
    )

    recipe_ingredients = relationship(
        "RecipeIngredient",
        back_populates="recipe"
    )


class Ingredient(Base):
    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), unique=True, nullable=False)

    recipes = relationship(
        "Recipe",
        secondary="recipe_ingredient",
        back_populates="ingredients",
        lazy="select"
    )
