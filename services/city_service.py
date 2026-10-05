from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from models.city import City
from repositories.city_repository import CityRepository
from repositories.like_repository import LikeRepository

from core.current_user import CURRENT_USER_ID

DEFAULT_IMAGE_URL = "/static/img/default-city.jpg"
DEFAULT_VIDEO_URL = "/static/img/default-city.mp4"

class CityService:
    """Бизнес-логика: заглушки медиа, правила черновика/публикации, выдача данных для шаблонов."""

    def __init__(self, db: AsyncSession):
        self.cities = CityRepository(db)
        self.likes = LikeRepository(db)

    def _with_media_defaults(self, city: City) -> City:
        if not city.image_url:
            city.image_url = DEFAULT_IMAGE_URL
        if not city.video_url:
            city.video_url = DEFAULT_VIDEO_URL
        return city

    def _serialize(self, city: City, likes_count: int) -> dict:
        return {
            "id": city.id,
            "name": city.name,
            "description": city.description,
            "route": city.route,
            "lat": city.lat,
            "lon": city.lon,
            "image_url": city.image_url,
            "video_url": city.video_url,
            "likes_count": likes_count,
        }

    # ---------- Лента: одна карточка за раз, напрямую из БД ----------
    async def get_feed_entry(self, city_id: int | None) -> tuple[dict | None, int | None]:
        city = None
        if city_id is not None:
            city = await self.cities.get_by_id(city_id)
            if city is None or city.status != "published":
                city = None

        if city is None:
            city = await self.cities.get_next_published(None)  # самый новый опубликованный

        if city is None:
            return None, None

        city = self._with_media_defaults(city)
        likes_count = await self.likes.count_for_city(city.id)

        next_city = await self.cities.get_next_published(city.id)
        next_city_id = next_city.id if next_city else None

        return self._serialize(city, likes_count), next_city_id

    # ---------- Плитка ----------
    async def get_grid_entries(self, lat_max: float | None) -> list[dict]:
        cities = await self.cities.get_published_filtered(lat_max=lat_max)
        likes_map = await self.likes.count_map([c.id for c in cities])
        return [
            self._serialize(self._with_media_defaults(c), likes_map.get(c.id, 0))
            for c in cities
        ]

    # ---------- Добавление / публикация ----------
    async def get_add_page_data(self) -> City | None:
        draft = await self.cities.get_draft(CURRENT_USER_ID)
        if draft:
            draft = self._with_media_defaults(draft)
        return draft

    async def create_draft(self, name: str) -> None:
        existing = await self.cities.get_draft(CURRENT_USER_ID)
        if existing or not name.strip():
            return

        new_city = City(name=name.strip(), status="draft", creator_id=CURRENT_USER_ID)
        self.cities.add(new_city)
        await self.cities.commit()

    async def publish_draft(self, city_id: int, description: str, route: str,
                             lat: float, lon: float) -> None:
        city = await self.cities.get_by_id(city_id)
        if city is None or city.status != "draft" or city.creator_id != CURRENT_USER_ID:
            return

        city.description = description.strip()
        city.route = route.strip()
        city.lat = lat
        city.lon = lon
        city.status = "published"
        city.published_at = datetime.now(timezone.utc)
        await self.cities.commit()

    # ---------- Удаление ----------
    async def delete_city(self, city_id: int) -> None:
        await self.cities.soft_delete(city_id)
        await self.cities.commit()
