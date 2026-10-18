from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.current_user import get_current_user_id, get_optional_user_id
from db.session import get_db
from schemas.city import (
    CityCardOut, CityFeedOut, CityOut, CityPublishIn, LikeIn, LikeOut,
)
from schemas.common import ErrorOut
from services.city_api_service import CityApiService

router = APIRouter(prefix="/api/cities", tags=["Услуги (города)"])

R401 = {401: {"model": ErrorOut, "description": "Не авторизован (нет куки или сессия истекла)"}}
R403 = {403: {"model": ErrorOut, "description": "Услуга принадлежит другому пользователю"}}
R404 = {404: {"model": ErrorOut, "description": "Не найдено"}}
R409 = {409: {"model": ErrorOut, "description": "Недопустимое состояние услуги"}}


def get_service(db: AsyncSession = Depends(get_db)) -> CityApiService:
    return CityApiService(db)


# ---------- Чтение: доступно гостю ----------

@router.get(
    "",
    response_model=list[CityCardOut],
    summary="Список опубликованных с фильтрацией",
    description=(
        "Публичный метод. Возвращает опубликованные услуги (города), отсортированные по названию. "
        "`lat_max` — широта не больше заданной. Для гостя `is_mine` всегда 0."
    ),
)
async def list_cities(
    lat_max: float | None = Query(None, description="Максимальная широта", examples=[55.0]),
    user_id: int | None = Depends(get_optional_user_id),
    service: CityApiService = Depends(get_service),
):
    return await service.list_published(user_id, lat_max)


@router.get(
    "/feed",
    response_model=CityFeedOut,
    summary="Лента без id (самая новая)",
    description="Публичный метод. Возвращает самую недавно опубликованную услугу.",
    responses=R404,
)
async def feed_first(
    user_id: int | None = Depends(get_optional_user_id),
    service: CityApiService = Depends(get_service),
):
    return await service.get_feed(user_id, None, False)


@router.get(
    "/feed/{city_id}",
    response_model=CityFeedOut,
    summary="Лента по id (?next=true даёт следующую)",
    description=(
        "Публичный метод. Без параметра возвращает услугу с указанным id; "
        "с `next=true` — следующую по ленте (опубликованную раньше), после последней — снова самую новую."
    ),
    responses=R404,
)
async def feed_by_id(
    city_id: int,
    next_: bool = Query(False, alias="next", description="Вернуть следующую услугу вместо указанной"),
    user_id: int | None = Depends(get_optional_user_id),
    service: CityApiService = Depends(get_service),
):
    return await service.get_feed(user_id, city_id, next_)


# ---------- Методы создателя: нужна авторизация ----------

@router.get(
    "/draft",
    response_model=CityOut,
    summary="Черновик текущего пользователя",
    description="Метод создателя. Возвращает незавершённый черновик услуги (фото, видео, название).",
    responses={**R401, **R404},
)
async def get_draft(
    user_id: int = Depends(get_current_user_id),
    service: CityApiService = Depends(get_service),
):
    return await service.get_draft(user_id)


@router.post(
    "",
    response_model=CityOut,
    status_code=201,
    summary="Создание черновика с фото и видео",
    description=(
        "Метод создателя. Загружает фото (jpeg/png/webp, до 5 МБ) и видео (mp4/webm, до 50 МБ) в MinIO "
        "и создаёт черновик. Создатель (`creator_id`) подставляется автоматически из сессии. "
        "У пользователя может быть только один черновик."
    ),
    responses={
        **R401,
        400: {"model": ErrorOut, "description": "Пустое название или файл"},
        409: {"model": ErrorOut, "description": "Черновик уже существует"},
        413: {"model": ErrorOut, "description": "Файл слишком большой"},
        415: {"model": ErrorOut, "description": "Недопустимый тип файла"},
    },
)
async def create_city(
    name: str = Form(..., description="Название города", examples=["Ростов-на-Дону"]),
    photo: UploadFile = File(..., description="Фото города"),
    video: UploadFile = File(..., description="Видео города"),
    user_id: int = Depends(get_current_user_id),
    service: CityApiService = Depends(get_service),
):
    return await service.create_draft(user_id, name, photo, video)


@router.put(
    "/{city_id}/publish",
    response_model=CityOut,
    summary="Публикация (draft → published)",
    description=(
        "Метод создателя. Заполняет описание, дорогу и координаты и переводит свой черновик в статус "
        "`published`. Гость получает 401, чужая услуга — 403."
    ),
    responses={**R401, **R403, **R404, **R409},
)
async def publish_city(
    city_id: int,
    data: CityPublishIn,
    user_id: int = Depends(get_current_user_id),
    service: CityApiService = Depends(get_service),
):
    return await service.publish(user_id, city_id, data)


@router.delete(
    "/{city_id}",
    status_code=204,
    summary="Мягкое удаление",
    description="Метод создателя. Переводит свою услугу в статус `deleted` (запись остаётся в БД).",
    responses={**R401, **R403, **R404, **R409},
)
async def delete_city(
    city_id: int,
    user_id: int = Depends(get_current_user_id),
    service: CityApiService = Depends(get_service),
):
    await service.delete(user_id, city_id)
    return Response(status_code=204)


@router.post(
    "/{city_id}/like",
    response_model=LikeOut,
    summary="Лайк (1) или отмена лайка (0)",
    description="Метод авторизованного пользователя. Лайкать можно только опубликованные услуги; повторный лайк идемпотентен.",
    responses={**R401, **R404, **R409},
)
async def like_city(
    city_id: int,
    data: LikeIn,
    user_id: int = Depends(get_current_user_id),
    service: CityApiService = Depends(get_service),
):
    return await service.set_like(user_id, city_id, data.like)
