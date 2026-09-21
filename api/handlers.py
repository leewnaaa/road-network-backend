from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from data.collections import cities_db, get_construction_cost
import uuid
import os

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

@router.get("/")
def get_catalog(request: Request):
    enriched_cities = []
    for city in cities_db:
        city_copy = city.copy()
        city_copy["cost"] = get_construction_cost(city)
        city_copy["likes_count"] = len(city_copy.get("likes", []))
        enriched_cities.append(city_copy)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"cities": enriched_cities}
    )

@router.get("/grid")
def get_grid(request: Request):
    enriched_cities = []
    for city in cities_db:
        city_copy = city.copy()
        city_copy["cost"] = get_construction_cost(city)
        city_copy["likes_count"] = len(city_copy.get("likes", []))
        enriched_cities.append(city_copy)
    return templates.TemplateResponse(
        request=request,
        name="city.html",
        context={"cities": enriched_cities}
    )

@router.get("/add")
def show_add_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="add.html",
        context={"cities": cities_db}
    )

@router.post("/add")
async def add_city(
    name: str = Form(...),
    lat: float = Form(...),
    lon: float = Form(...),
    route: str = Form(...),
    description: str = Form(""),
    parent: str = Form(""),
):
    """Добавляет новый город в сеть. Медиафайлы пока не сохраняются на сервере,
    поэтому для фото/видео используются заглушки."""
    if not name.strip():
        return JSONResponse({"error": "Название города обязательно"}, status_code=400)

    new_id = max((c["id"] for c in cities_db), default=0) + 1
    clean_description = description.strip() or f"Новый узел дорожной сети — {name.strip()}."

    new_city = {
        "id": new_id,
        "name": name.strip(),
        "lat": lat,
        "lon": lon,
        "route": route.strip(),
        "parent": parent.strip() if parent and parent.strip() else None,
        "description": clean_description,
        "details": "Подробная информация об этом участке скоро появится.",
        "likes": [],
        "image_url": f"https://picsum.photos/400/300?random={new_id}",
        "video_url": "https://www.w3schools.com/html/mov_bbb.mp4",
    }

    cities_db.append(new_city)

    return JSONResponse({"success": True, "id": new_id})

@router.post("/like/{city_id}")
def like_city(city_id: int):
    """Добавляет нового пользователя в массив лайков"""
    city = next((c for c in cities_db if c["id"] == city_id), None)
    if city:
        new_user_id = f"user_{uuid.uuid4().hex[:8]}"
        city.setdefault("likes", []).append(new_user_id)
        return JSONResponse({"likes_count": len(city["likes"])})
    return JSONResponse({"error": "City not found"}, status_code=404)
