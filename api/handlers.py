from datetime import datetime, timezone
import os

from fastapi import APIRouter, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.city import City
from models.like import Like
from models.user import User

router = APIRouter()
templates = Jinja2Templates(directory="templates")

STATIC_CSS_PATH = os.path.join("static", "css", "style.css")


def css_version():
    """Версия CSS-файла = время его последнего изменения на диске.
    Как только style.css меняется, ссылка в шаблоне меняется автоматически
    (?v=<новое_время>), и браузер больше не берёт файл из кэша."""
    try:
        return int(os.path.getmtime(STATIC_CSS_PATH))
    except OSError:
        return 0


templates.env.globals["css_version"] = css_version

# Авторизации в проекте нет, поэтому все действия выполняются
# от лица тестового пользователя (см. INSERT INTO users в Adminer).
CURRENT_USER_ID = 1

# Заглушки для случаев, когда у услуги нет фото/видео (или они недоступны по URL)
DEFAULT_IMAGE_URL = "http://localhost:9000/media/vyvody-dorozhnoe-stroitelstvo.jpg"
DEFAULT_VIDEO_URL = "/static/img/default-city.mp4"


def _with_media_defaults(city: City) -> City:
    if not city.image_url:
        city.image_url = DEFAULT_IMAGE_URL
    if not city.video_url:
        city.video_url = DEFAULT_VIDEO_URL
    return city


async def _get_likes_map(db: AsyncSession, city_ids: list[int]) -> dict[int, int]:
    """Возвращает {city_id: количество лайков} одним запросом (без N+1)."""
    if not city_ids:
        return {}
    result = await db.execute(select(Like.city_id).where(Like.city_id.in_(city_ids)))
    counts: dict[int, int] = {}
    for (city_id,) in result.all():
        counts[city_id] = counts.get(city_id, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# 1. GET / — лента (reels-плеер), только опубликованные услуги
# ---------------------------------------------------------------------------
@router.get("/")
async def get_feed(request: Request, city_id: int | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(City).where(City.status == "published").order_by(City.published_at.desc())
    result = await db.execute(stmt)
    cities = result.scalars().all()

    likes_map = await _get_likes_map(db, [c.id for c in cities])

    enriched = []
    for city in cities:
        city = _with_media_defaults(city)
        enriched.append({
            "id": city.id,
            "name": city.name,
            "description": city.description,
            "route": city.route,
            "image_url": city.image_url,
            "video_url": city.video_url,
            "likes_count": likes_map.get(city.id, 0),
        })

    current_index = 0
    if city_id is not None:
        for i, c in enumerate(enriched):
            if c["id"] == city_id:
                current_index = i
                break

    current_city = enriched[current_index] if enriched else None
    next_city_id = enriched[(current_index + 1) % len(enriched)]["id"] if enriched else None

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"current_city": current_city, "next_city_id": next_city_id},
    )


# ---------------------------------------------------------------------------
# 2. GET /grid — плитка с фильтрами (через GET-параметры, без JS)
# ---------------------------------------------------------------------------
@router.get("/grid")
async def get_grid(
    request: Request,
    route: str = "",
    search: str = "",
    lat_max: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(City).where(City.status == "published")

    if route:
        stmt = stmt.where(City.route == route)
    if search:
        stmt = stmt.where(City.name.ilike(f"%{search}%"))
    if lat_max is not None:
        stmt = stmt.where(City.lat <= lat_max)

    result = await db.execute(stmt.order_by(City.name))
    cities = result.scalars().all()

    likes_map = await _get_likes_map(db, [c.id for c in cities])

    enriched = []
    for city in cities:
        city = _with_media_defaults(city)
        enriched.append({
            "id": city.id,
            "name": city.name,
            "route": city.route,
            "lat": city.lat,
            "lon": city.lon,
            "image_url": city.image_url,
            "likes_count": likes_map.get(city.id, 0),
        })

    return templates.TemplateResponse(
        request=request,
        name="city.html",
        context={
            "cities": enriched,
            "route": route,
            "search": search,
            "lat_max": lat_max if lat_max is not None else 70,
        },
    )


# ---------------------------------------------------------------------------
# 3. GET /add — форма создания черновика ИЛИ публикации существующего
# ---------------------------------------------------------------------------
@router.get("/add")
async def show_add_form(request: Request, db: AsyncSession = Depends(get_db)):
    stmt = select(City).where(City.creator_id == CURRENT_USER_ID, City.status == "draft")
    result = await db.execute(stmt)
    draft = result.scalar_one_or_none()

    if draft:
        draft = _with_media_defaults(draft)

    parent_options_stmt = select(City).where(City.status == "published")
    parent_result = await db.execute(parent_options_stmt)
    parent_options = parent_result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="add.html",
        context={"draft": draft, "parent_options": parent_options},
    )


# ---------------------------------------------------------------------------
# 4. POST /add — создание черновика (ORM)
# ---------------------------------------------------------------------------
@router.post("/add")
async def create_draft(
    name: str = Form(...),
    description: str = Form(""),
    route: str = Form(""),
    lat: str = Form(""),
    lon: str = Form(""),
    parent_id: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(City).where(City.creator_id == CURRENT_USER_ID, City.status == "draft")
    result = await db.execute(stmt)
    existing_draft = result.scalar_one_or_none()

    if not existing_draft and name.strip():
        new_city = City(
            name=name.strip(),
            status="draft",
            creator_id=CURRENT_USER_ID,
            description=description.strip() or None,
            route=route.strip() or None,
            lat=float(lat) if lat.strip() else None,
            lon=float(lon) if lon.strip() else None,
            parent_id=int(parent_id) if parent_id.strip() else None,
        )
        db.add(new_city)
        await db.commit()

    return RedirectResponse(url="/add", status_code=303)


# ---------------------------------------------------------------------------
# 5. POST /add/{city_id}/publish — публикация черновика (ORM)
# ---------------------------------------------------------------------------
@router.post("/add/{city_id}/publish")
async def publish_city(
    city_id: int,
    description: str = Form(...),
    route: str = Form(...),
    lat: float = Form(...),
    lon: float = Form(...),
    parent_id: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(City).where(City.id == city_id, City.creator_id == CURRENT_USER_ID)
    result = await db.execute(stmt)
    city = result.scalar_one_or_none()

    if city and city.status == "draft":
        city.description = description.strip()
        city.route = route.strip()
        city.lat = lat
        city.lon = lon
        city.parent_id = int(parent_id) if parent_id.strip() else None
        city.status = "published"
        city.published_at = datetime.now(timezone.utc)
        await db.commit()

    return RedirectResponse(url="/grid", status_code=303)


# ---------------------------------------------------------------------------
# 6. POST /{city_id}/delete — мягкое удаление через SQL-курсор (без ORM)
# ---------------------------------------------------------------------------
@router.post("/{city_id}/delete")
async def delete_city(city_id: int, db: AsyncSession = Depends(get_db)):
    update_query = """
        UPDATE cities
        SET status = 'deleted'
        WHERE id = :id
    """
    await db.execute(text(update_query), {"id": city_id})
    await db.commit()

    return RedirectResponse(url="/grid", status_code=303)
