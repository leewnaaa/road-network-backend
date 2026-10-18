from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

from core.minio_client import ensure_bucket
from core.redis_client import close_redis

from api.routers.city_router import router as pages_router
from api.routers.city_api_router import router as city_api_router

from api.routers.user_api_router import router as user_api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_bucket()
    yield
    await close_redis()


app = FastAPI(
    title="ДОРСЕТЬ - Дорожная сеть",
    description=(
        "Веб-сервис «Строительство дорожной сети».\n\n"
        "**Гость** может только читать данные (список услуг, лента). "
        "**Создатель** после `POST /api/users/login` получает сессионную куку и может создавать, "
        "публиковать и удалять свои услуги, ставить лайки."
    ),
    version="4.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static"), name="static")
# HTML-страницы старого интерфейса скрыты из Swagger: в нём только REST API
app.include_router(pages_router, include_in_schema=False)
app.include_router(city_api_router)

app.include_router(user_api_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
