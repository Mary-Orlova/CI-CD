from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .database import get_db
import schemas, models


router = APIRouter(
    prefix="/recipes",
    tags=["Recipes"]
)


@router.get("/")
async def get_all_recipes(db: AsyncSession = Depends(get_db)):
    """
    Get-функция (получение всех рецептов) с сортировкой:
    - По убыванию просмотров
    - При одинаковых просмотрах по времени готовки
    """
    query = select(models.Recipe).order_by(models.Recipe.views.desc(), models.Recipe.cook_time)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{recipe_id}", response_model=schemas.RecipeOut)
async def get_recipe_detail(recipe_id: int, db: AsyncSession = Depends(get_db)):
    """Get-функция (получение рецепта по recipe_id)
     Предоставляет пользователю детальную информацию о рецепте, при этом увеличивает счетчик просмотра"""


    query = select(models.Recipe).where(models.Recipe.id == recipe_id).options(
        selectinload(models.Recipe.ingredients),
        selectinload(models.Recipe.recipe_ingredients)  # Предварительная загрузка ассоциативной таблицы
    )

    result = await db.execute(query)
    recipe = result.scalar_one_or_none()

    if not recipe:
        raise HTTPException(status_code=404, detail="Рецепт не найден")

    recipe.views += 1
    await db.commit()
    await db.refresh(recipe)

    recipe_dict = recipe.__dict__
    recipe_dict['ingredients'] = [
        {
            "id": ing.id,
            "title": ing.title,
            "quantity": next((ri.quantity for ri in recipe.recipe_ingredients if ri.ingredient_id == ing.id), None)
        }
        for ing in recipe.ingredients
    ]
    return schemas.RecipeOut(**recipe_dict)


@router.post("/", response_model=schemas.RecipeOut)
async def create_recipe(
        recipe: schemas.RecipeCreate,
        db: AsyncSession = Depends(get_db),
        important: bool = Query(True, title='Important', description='Полезный рецепт?')
):
    """
    Post-функция, создает рецепт.
    Валидация на уникальность названия, время готовки должно быть больше 0 минут, а так же минимум 1 ингредиент
    """
    existing = await db.execute(
        select(models.Recipe).where(models.Recipe.title == recipe.title)
    )

    if existing.scalar():
        raise HTTPException(400, "Ошибка! Рецепт с таким названием уже существует")

 # Создаем рецепт
    new_recipe = models.Recipe(
        title=recipe.title,
        description=recipe.description,
        cook_time=recipe.cook_time,
    )
    db.add(new_recipe)
    await db.commit()
    await db.refresh(new_recipe)

    # Добавляем ингредиенты с quantity
    for ingredient in recipe.ingredients:
        # Ищем или создаем ингредиент
        db_ingredient = await db.execute(
            select(models.Ingredient).where(
                models.Ingredient.title == ingredient.title
            )
        )
        db_ingredient = db_ingredient.scalar_one_or_none()

        if not db_ingredient:
            db_ingredient = models.Ingredient(title=ingredient.title)
            db.add(db_ingredient)
            await db.commit()
            await db.refresh(db_ingredient)

        # Создаем связь с quantity
        association = models.RecipeIngredient(
            recipe_id=new_recipe.id,
            ingredient_id=db_ingredient.id,
            quantity=ingredient.quantity
        )
        db.add(association)

    await db.commit()

    # Явная загрузка отношений
    query = select(models.Recipe).where(models.Recipe.id == new_recipe.id).options(
        selectinload(models.Recipe.ingredients),
        selectinload(models.Recipe.recipe_ingredients)
    )
    result = await db.execute(query)
    new_recipe = result.scalar_one_or_none()

    # Преобразование ингредиентов в нужный формат перед сериализацией
    recipe_dict = {
        "id": new_recipe.id,
        "title": new_recipe.title,
        "description": new_recipe.description,
        "cook_time": new_recipe.cook_time,
        "views": new_recipe.views,
        "ingredients": [
            {
                "id": ing.id,
                "title": ing.title,
                "quantity": next(
                    (ri.quantity for ri in new_recipe.recipe_ingredients if ri.ingredient_id == ing.id),
                    None
                )
            }
            for ing in new_recipe.ingredients
        ]
    }

    return schemas.RecipeOut(**recipe_dict)


@router.patch("/{recipe_id}", response_model=schemas.RecipeOut)
async def update_recipe(
        recipe_id: int,
        recipe_data: schemas.RecipeUpdate,
        session: AsyncSession = Depends(get_db)
):
    """Patch-функция. Частичное обновление рецепта с ингредиентами"""

    try:
        # Загрузка рецепта с ингредиентами
        result = await session.execute(
            select(models.Recipe)
            .options(selectinload(models.Recipe.recipe_ingredients))
            .where(models.Recipe.id == recipe_id)
        )
        recipe = result.scalar_one_or_none()

        if not recipe:
            raise HTTPException(status_code=404, detail="Рецепт не найден")

        # Обновление основных полей
        update_data = recipe_data.dict(exclude_unset=True)
        for field in ['title', 'cook_time', 'description']:
            if field in update_data:
                setattr(recipe, field, update_data[field])

        # Обработка ингредиентов
        if recipe_data.ingredients is not None:
            # Удаляем старые связи
            for ri in recipe.recipe_ingredients:
                await session.delete(ri)

            # Создаём новые
            for ingredient_in in recipe_data.ingredients:
                # Поиск или создание ингредиента
                result = await session.execute(
                    select(models.Ingredient)
                    .where(models.Ingredient.title == ingredient_in.title)
                )
                ingredient = result.scalar_one_or_none()

                if not ingredient:
                    ingredient = models.Ingredient(title=ingredient_in.title)
                    session.add(ingredient)
                    await session.flush()  # Получаем ID нового ингредиента

                # Создание связи
                recipe_ingredient = models.RecipeIngredient(
                    recipe_id=recipe_id,
                    ingredient_id=ingredient.id,
                    quantity=ingredient_in.quantity
                )
                session.add(recipe_ingredient)

        await session.commit()
        await session.refresh(recipe)
        return recipe

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{recipe_id}")
async def delete_recipe(
    recipe_id: int,
    session: AsyncSession = Depends(get_db)
):
    """Удаление рецепта с каскадным удалением связей"""
    try:
        # Поиск рецепта с предварительной загрузкой связей
        result = await session.execute(
            select(models.Recipe)
            .options(selectinload(models.Recipe.recipe_ingredients))
            .where(models.Recipe.id == recipe_id)
        )
        recipe = result.scalar_one_or_none()

        if not recipe:
            raise HTTPException(
                status_code=404,
                detail="Рецепт не найден"
            )

        await session.execute(
            delete(models.RecipeIngredient)
            .where(models.RecipeIngredient.recipe_id == recipe_id)
        )

        # Удаление основного объекта
        await session.delete(recipe)
        await session.commit()

        # Возвращаем пустой ответ с кодом 204
        return Response(status_code=204)

    except HTTPException:
        # Пробрасываем уже обработанные ошибки
        raise

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при удалении рецепта: {str(e)}"
        )
