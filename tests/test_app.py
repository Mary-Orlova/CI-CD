import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.database import Base, get_db
from src.models import Recipe, RecipeIngredient, Ingredient
from src.main import app
import asyncio  # Import asyncio

# Use an in-memory SQLite database for testing
DATABASE_URL_TEST = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(DATABASE_URL_TEST, echo=True)
TestingSessionLocal = sessionmaker(
    engine_test,
    class_=AsyncSession,
    expire_on_commit=False
)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session")
async def async_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def client(async_db):
    async with AsyncClient(app=app, base_url="http://test") as async_client:
        yield async_client

@pytest.mark.asyncio
async def test_get_all_recipes(client):
    response = await client.get("/recipes/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_read_recipe_by_id(client):
    # Create a recipe first
    recipe_data = {"title": "Test Recipe", "description": "Test Description", "cook_time": 30, "ingredients": [{"title": "Flour", "quantity": "1 cup"}]}  # Include ingredients
    response = await client.post("/recipes/", json=recipe_data)
    assert response.status_code == 200, f"Expected 200, but got {response.status_code} with content: {response.text}"
    created_recipe = response.json()
    recipe_id = created_recipe["id"]

    response = await client.get(f"/recipes/{recipe_id}")
    assert response.status_code == 200,  f"Expected 200, but got {response.status_code} with content: {response.text}"
    data = response.json()
    assert data["id"] == recipe_id
    assert data["title"] == "Test Recipe"

@pytest.mark.asyncio
async def test_create_recipe(client):
    recipe_data = {
        "title": "New Test Recipe",
        "description": "New Test Description",
        "cook_time": 45,
        "ingredients": [{"title": "Tomato", "quantity": "2"}]
    }
    response = await client.post("/recipes/", json=recipe_data)
    assert response.status_code == 200,  f"Expected 200, but got {response.status_code} with content: {response.text}"
    data = response.json()
    assert data["title"] == recipe_data["title"]
    assert data["cook_time"] == recipe_data["cook_time"]
    assert len(data["ingredients"]) == 1

@pytest.mark.asyncio
async def test_update_recipe(client):
    # Create a recipe first
    recipe_data = {"title": "Old Recipe", "description": "Old Description", "cook_time": 60, "ingredients": [{"title": "Flour", "quantity": "1 cup"}]}  # Include ingredients
    create_response = await client.post("/recipes/", json=recipe_data)
    assert create_response.status_code == 200, f"Expected 200, but got {create_response.status_code} with content: {create_response.text}"
    created_recipe = create_response.json()
    recipe_id = created_recipe["id"]

    # Update the recipe
    update_data = {"title": "Updated Recipe", "description": "Updated Description", "cook_time": 20, "ingredients": [{"title": "Sugar", "quantity": "1/2 cup"}]}  # Include ingredients
    response = await client.patch(f"/recipes/{recipe_id}", json=update_data)
    assert response.status_code == 200, f"Expected 200, but got {response.status_code} with content: {response.text}"
    data = response.json()
    assert data["title"] == update_data["title"]
    assert data["description"] == update_data["description"]
    assert data["cook_time"] == update_data["cook_time"]

@pytest.mark.asyncio
async def test_delete_recipe(client):
    # Create a recipe first
    recipe_data = {"title": "Recipe to Delete", "description": "Description to Delete", "cook_time": 30, "ingredients": [{"title": "Salt", "quantity": "1 tsp"}]}  # Include ingredients
    create_response = await client.post("/recipes/", json=recipe_data)
    assert create_response.status_code == 200, f"Expected 200, but got {create_response.status_code} with content: {create_response.text}"
    created_recipe = create_response.json()
    recipe_id = created_recipe["id"]

    # Delete the recipe
    response = await client.delete(f"/recipes/{recipe_id}")
    assert response.status_code == 204, f"Expected 204, but got {response.status_code} with content: {response.text}"

    # Verify the recipe is deleted
    response = await client.get(f"/recipes/{recipe_id}")
    assert response.status_code == 404, f"Expected 404, but got {response.status_code} with content: {response.text}"
