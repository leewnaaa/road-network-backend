from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.current_user import get_current_user_id
from db.session import get_db
from schemas.city import (
    CityCardOut, CityFeedOut, CityOut, CityPublishIn, LikeIn, LikeOut,
)
from services.city_api_service import CityApiService

router = APIRouter(prefix="/api/cities", tags=["Услуги (города)"])


def get_service(db: AsyncSession = Depends(get_db)) -> CityApiService:
    return CityApiService(db)


@router.get("", response_model=list[CityCardOut], summary="Список опубликованных с фильтрацией")
async def list_cities(
    route: str = "",
    search: str = "",
    lat_max: float | None = None,
    user_id: int = Depends(get_current_user_id),
    service: CityApiService = Depends(get_service),
):
    return await service.list_published(user_id, route, search, lat_max)


# --- статические пути объявлены раньше путей с {city_id} ---
@router.get("/feed", response_model=CityFeedOut, summary="Лента без id (самая новая)")
async def feed_first(
    user_id: int = Depends(get_current_user_id),
    service: CityApiService = Depends(get_service),
):
    return await service.get_feed(user_id, None, False)


@router.get("/feed/{city_id}", response_model=CityFeedOut, summary="Лента по id (?next=true даёт следующую)")
async def feed_by_id(
    city_id: int,
    next_: bool = Query(False, alias="next"),
    user_id: int = Depends(get_current_user_id),
    service: CityApiService = Depends(get_service),
):
    return await service.get_feed(user_id, city_id, next_)


@router.get("/draft", response_model=CityOut, summary="Черновик текущего пользователя")
async def get_draft(
    user_id: int = Depends(get_current_user_id),
    service: CityApiService = Depends(get_service),
):
    return await service.get_draft(user_id)


@router.post("", response_model=CityOut, status_code=201, summary="Создание черновика с фото и видео")
async def create_city(
    name: str = Form(...),
    photo: UploadFile = File(...),
    video: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    service: CityApiService = Depends(get_service),
):
    return await service.create_draft(user_id, name, photo, video)


@router.put("/{city_id}/publish", response_model=CityOut, summary="Публикация (draft → published)")
async def publish_city(
    city_id: int,
    data: CityPublishIn,
    user_id: int = Depends(get_current_user_id),
    service: CityApiService = Depends(get_service),
):
    return await service.publish(user_id, city_id, data)


@router.delete("/{city_id}", status_code=204, summary="Мягкое удаление")
async def delete_city(
    city_id: int,
    user_id: int = Depends(get_current_user_id),
    service: CityApiService = Depends(get_service),
):
    await service.delete(user_id, city_id)
    return Response(status_code=204)


@router.post("/{city_id}/like", response_model=LikeOut, summary="Лайк (1) или отмена лайка (0)")
async def like_city(
    city_id: int,
    data: LikeIn,
    user_id: int = Depends(get_current_user_id),
    service: CityApiService = Depends(get_service),
):
    return await service.set_like(user_id, city_id, data.like)
