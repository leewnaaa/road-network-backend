from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.templating import templates
from db.session import get_db
from services.city_service import CityService

router = APIRouter()


@router.get("/")
async def get_feed(request: Request, city_id: int | None = None, db: AsyncSession = Depends(get_db)):
    service = CityService(db)
    current_city, next_city_id = await service.get_feed_entry(city_id)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"current_city": current_city, "next_city_id": next_city_id},
    )


@router.get("/cities")
async def get_grid(
    request: Request,
    lat_max: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    service = CityService(db)
    cities = await service.get_grid_entries(lat_max)
    return templates.TemplateResponse(
        request=request,
        name="city.html",
        context={
            "cities": cities,
            "lat_max": lat_max if lat_max is not None else 70,
        },
    )


@router.get("/cities/add")
async def show_add_form(request: Request, db: AsyncSession = Depends(get_db)):
    service = CityService(db)
    draft = await service.get_add_page_data()
    return templates.TemplateResponse(
        request=request,
        name="add.html",
        context={"draft": draft},
    )


@router.post("/cities/add")
async def create_draft(name: str = Form(...), db: AsyncSession = Depends(get_db)):
    service = CityService(db)
    await service.create_draft(name)
    return RedirectResponse(url="/cities/add", status_code=303)


@router.post("/cities/{city_id}/publish")
async def publish_city(
    city_id: int,
    description: str = Form(...),
    route: str = Form(...),
    lat: float = Form(...),
    lon: float = Form(...),
    db: AsyncSession = Depends(get_db),
):
    service = CityService(db)
    await service.publish_draft(city_id, description, route, lat, lon)
    return RedirectResponse(url="/cities", status_code=303)

@router.post("/cities/{city_id}/delete")
async def delete_city(city_id: int, db: AsyncSession = Depends(get_db)):
    service = CityService(db)
    await service.delete_city(city_id)
    return RedirectResponse(url="/cities", status_code=303)
