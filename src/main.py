from fastapi import FastAPI
from starlette.responses import JSONResponse

from .database import engine, Base
from router import router

app = FastAPI(
    title="Кулинарная книга API",
    description="API для управления рецептами с полной документацией",
    version="1.0.0"
)

@app.on_event("startup")
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error"},
    )

app.include_router(router)
