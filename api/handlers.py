from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from data.collections import cities_db, get_construction_cost
import uuid

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/")
def get_catalog(request: Request):
    enriched_cities = []
    for city in cities_db:
        city_copy = city.copy()
        city_copy["cost"] = get_construction_cost(city)
        city_copy["likes_count"] = len(city_copy.get("likes", []))  # Считаем длину массива
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

@router.post("/like/{city_id}")
def like_city(city_id: int):
    """Добавляет нового пользователя в массив лайков"""
    city = next((c for c in cities_db if c["id"] == city_id), None)
    if city:
        # Генерируем уникальный ID пользователя
        new_user_id = f"user_{uuid.uuid4().hex[:8]}"
        city.setdefault("likes", []).append(new_user_id)
        return JSONResponse({"likes_count": len(city["likes"])})
    return JSONResponse({"error": "City not found"}, status_code=404)
