from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

from api.routers.city_router import router
from core.minio_client import ensure_bucket

from api.routers.city_router import router as pages_router
from api.routers.city_api_router import router as city_api_router

from api.routers.user_api_router import router as user_api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_bucket()
    yield


app = FastAPI(title="ДОРСЕТЬ - Дорожная сеть", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)

app.include_router(pages_router)
app.include_router(city_api_router)

app.include_router(user_api_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
