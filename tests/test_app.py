import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.database import Base, get_db
from src.models import Recipe, RecipeIngredient, Ingredient
from src.main import app

# Конфигурация тестовой БД
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
async_engine = create_async_engine(TEST_DATABASE_URL, echo=True)

# Асинхронная сессия
TestingSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    """Инициализация и очистка тестовой БД"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    """Фикстура для HTTP-клиента с подменой зависимости БД"""
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_read_recipes(client):
    """Тест get-запроса (получения всех рецептов)"""
    response = await client.get("/recipes/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_read_recipe_by_id(client):
    """Тест get-запроса по id (получения рецепта по ID)"""

    async with TestingSessionLocal() as session:
        recipe = Recipe(title="Тестовый рецепт", description="Описание", cook_time=40)
        session.add(recipe)
        await session.commit()
        await session.refresh(recipe)

        recipe_id = recipe.id

    response = await client.get(f"/recipes/{recipe_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == recipe_id
    assert data["title"] == "Тестовый рецепт"


@pytest.mark.asyncio
async def test_create_recipe(client):
    """Тест post-запроса (создания нового рецепта)"""
    recipe_data = {
        "title": "Тестовый рецепт",
        "description": "Описание теста",
        "cook_time": 30,
        "ingredients": [{"title": "Ингредиент", "quantity": "100г"}]
    }

    response = await client.post("/recipes/", json=recipe_data)
    assert response.status_code == 200
    data = response.json()

    assert data["title"] == recipe_data["title"]
    assert data["cook_time"] == recipe_data["cook_time"]

    async with TestingSessionLocal() as session:
        result = await session.execute(select(Recipe))
        recipes = result.scalars().all()
        assert len(recipes) == 1
        assert recipes[0].title == recipe_data["title"]


@pytest.mark.asyncio
async def test_update_recipe(client):
    """Тест PATCH-запроса (частичное обновление рецепта)"""
    async with TestingSessionLocal() as session:
        recipe = Recipe(
            title="Старый рецепт",
            description="Старое описание",
            cook_time=60,
            views=0  # Добавляем проверку views
        )
        session.add(recipe)
        await session.commit()
        await session.refresh(recipe)

        recipe_id = recipe.id

    update_data = {
        "title": "Новый рецепт",
        "description": "Новое описание",
        "cook_time": 20,
        "ingredients": [{"title": "Ингредиент", "quantity": "100г"}]
    }

    response = await client.patch(f"/recipes/{recipe_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()

    # Проверка всех полей ответа
    assert data["id"] == recipe_id
    assert data["title"] == update_data["title"]
    assert data["description"] == update_data["description"]
    assert data["cook_time"] == update_data["cook_time"]
    assert data["views"] == 0  # Проверка неизменного поля

    # Проверка в БД
    async with TestingSessionLocal() as session:
        result = await session.execute(select(Recipe).where(Recipe.id == recipe_id))
        updated_recipe = result.scalar_one_or_none()
        assert updated_recipe.title == update_data["title"]
        assert updated_recipe.description == update_data["description"]
        assert updated_recipe.cook_time == update_data["cook_time"]
        assert updated_recipe.views == 0


@pytest.mark.asyncio
async def test_delete_recipe(client):
    """Тест DELETE-запроса (удаление рецепта)"""
    # Создаем рецепт с ингредиентом
    async with TestingSessionLocal() as session:
        ingredient = Ingredient(title="Томаты")
        session.add(ingredient)
        await session.commit()
        await session.refresh(ingredient)

        recipe = Recipe(
            title="Для удаления",
            description="Описание",
            cook_time=40,
            views=0
        )
        recipe_ingredient = RecipeIngredient(
            ingredient_id=ingredient.id,
            quantity="500 г"
        )
        recipe.recipe_ingredients.append(recipe_ingredient)
        session.add(recipe)
        await session.commit()
        await session.refresh(recipe)

        recipe_id = recipe.id

    response = await client.delete(f"/recipes/{recipe_id}")
    assert response.status_code == 204

    # Проверка отсутствия записей
    async with TestingSessionLocal() as session:
        # Проверка рецепта
        result = await session.execute(select(Recipe).where(Recipe.id == recipe_id))
        assert result.scalar_one_or_none() is None

        # Проверка связей
        result = await session.execute(
            select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe_id)
        )
        assert result.scalar_one_or_none() is None

        # Проверка ингредиента (должен остаться)
        result = await session.execute(select(Ingredient).where(Ingredient.id == ingredient.id))
        assert result.scalar_one_or_none() is not None
