import pytest
import pytest_asyncio
import os
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.database import Base, get_db
from src.models import Recipe, RecipeIngredient, Ingredient
from src.main import app

# Конфигурация тестовой БД
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
async_engine = create_async_engine(TEST_DATABASE_URL, echo=True)

# Асинхронная сессия
TestingSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """Инициализация и очистка тестовой БД"""
    if os.path.exists("test.db"):
        os.remove("test.db")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    if os.path.exists("test.db"):
        os.remove("test.db")


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
    recipe_data = {
        "title": "Тестовый рецепт",
        "description": "Описание",
        "cook_time": 40,
        "ingredients": [{"title": "Ингредиент", "quantity": "100г"}]
    }
    create_resp = await client.post("/recipes/", json=recipe_data)
    assert create_resp.status_code == 200
    recipe_id = create_resp.json()["id"]

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


@pytest.mark.asyncio
async def test_update_recipe(client):
    """Тест PATCH-запроса (частичное обновление рецепта)"""
    recipe_data = {
        "title": "Старый рецепт",
        "description": "Старое описание",
        "cook_time": 60,
        "ingredients": [{"title": "Ингредиент", "quantity": "100г"}]
    }
    create_resp = await client.post("/recipes/", json=recipe_data)
    assert create_resp.status_code == 200
    recipe_id = create_resp.json()["id"]

    update_data = {
        "title": "Новый рецепт",
        "description": "Новое описание",
        "cook_time": 20,
        "ingredients": [{"title": "Новый ингредиент", "quantity": "200г"}]
    }
    response = await client.patch(f"/recipes/{recipe_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == recipe_id
    assert data["title"] == update_data["title"]
    assert data["description"] == update_data["description"]
    assert data["cook_time"] == update_data["cook_time"]


@pytest.mark.asyncio
async def test_delete_recipe(client):
    """Тест DELETE-запроса (удаление рецепта)"""

    recipe_data = {
        "title": "Для удаления",
        "description": "Описание",
        "cook_time": 40,
        "ingredients": [{"title": "Ингредиент", "quantity": "100г"}]
    }
    create_resp = await client.post("/recipes/", json=recipe_data)
    assert create_resp.status_code == 200
    recipe_id = create_resp.json()["id"]

    response = await client.delete(f"/recipes/{recipe_id}")
    assert response.status_code == 204


    response = await client.get(f"/recipes/{recipe_id}")
    assert response.status_code == 404
