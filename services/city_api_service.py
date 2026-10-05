from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from models.city import City
from repositories.city_repository import CityRepository
from repositories.like_repository import LikeRepository
from schemas.city import (
    CityCardOut, CityFeedOut, CityOut, CityPublishIn, LikeOut,
)
from services.storage_service import StorageService

# Из какого статуса в какой можно перейти. Вернуть в черновик нельзя.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"published", "deleted"},
    "published": {"deleted"},
    "deleted": set(),
}


class CityApiService:
    """Бизнес-логика домена услуг для REST API."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.cities = CityRepository(db)
        self.likes = LikeRepository(db)
        self.storage = StorageService()

    # ---------- вспомогательное ----------
    async def _get_visible(self, city_id: int) -> City:
        """Удалённые клиенту не передаются: для него их как будто нет."""
        city = await self.cities.get_by_id(city_id)
        if city is None or city.status == "deleted":
            raise HTTPException(404, "Услуга не найдена")
        return city

    async def _get_own(self, user_id: int, city_id: int) -> City:
        city = await self._get_visible(city_id)
        if city.creator_id != user_id:
            raise HTTPException(403, "Это услуга другого пользователя")
        return city

    @staticmethod
    def _move(city: City, new_status: str) -> None:
        if new_status not in ALLOWED_TRANSITIONS[city.status]:
            raise HTTPException(409, f"Нельзя перевести услугу из «{city.status}» в «{new_status}»")
        city.status = new_status

    async def _feed_out(self, city: City, user_id: int) -> CityFeedOut:
        likes_count = await self.likes.count_for_city(city.id)
        liked = await self.likes.is_liked(user_id, city.id)
        return CityFeedOut.from_city(city, likes_count, user_id, liked_by_me=int(liked))

    # ---------- GET список с фильтрацией ----------
    async def list_published(
        self, user_id: int, route: str, search: str, lat_max: float | None
    ) -> list[CityCardOut]:
        cities = await self.cities.get_published_filtered(
            route=route, search=search, lat_max=lat_max
        )
        likes_map = await self.likes.count_map([c.id for c in cities])
        return [CityCardOut.from_city(c, likes_map.get(c.id, 0), user_id) for c in cities]

    # ---------- GET лента ----------
    async def get_feed(self, user_id: int, city_id: int | None, next_: bool) -> CityFeedOut:
        if city_id is None:
            city = await self.cities.get_newest_published()
        else:
            city = await self.cities.get_by_id(city_id)
            if city is None or city.status != "published":
                raise HTTPException(404, "Услуга не найдена в ленте")
            if next_:
                city = (
                    await self.cities.get_older_published(city)
                    or await self.cities.get_newest_published()   # дошли до конца, начинаем заново
                )
        if city is None:
            raise HTTPException(404, "Опубликованных услуг пока нет")
        return await self._feed_out(city, user_id)

    # ---------- GET черновик ----------
    async def get_draft(self, user_id: int) -> CityOut:
        draft = await self.cities.get_draft(user_id)
        if draft is None:
            raise HTTPException(404, "Черновика нет")
        return CityOut.from_city(draft)

    # ---------- POST добавление ----------
    async def create_draft(
        self, user_id: int, name: str, photo: UploadFile, video: UploadFile
    ) -> CityOut:
        name = name.strip()
        if not name:
            raise HTTPException(400, "Название не может быть пустым")
        if await self.cities.get_draft(user_id):
            raise HTTPException(409, "У вас уже есть черновик: опубликуйте или удалите его")

        image_name = await self.storage.upload(photo, "image")
        try:
            video_name = await self.storage.upload(video, "video")
        except Exception:
            await self.storage.delete(image_name)
            raise

        city = City(
            name=name,
            status="draft",
            creator_id=user_id,
            image_url=image_name,
            video_url=video_name,
        )
        self.cities.add(city)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            await self.storage.delete(image_name)
            await self.storage.delete(video_name)
            raise
        return CityOut.from_city(city)

    # ---------- PUT публикация ----------
    async def publish(self, user_id: int, city_id: int, data: CityPublishIn) -> CityOut:
        city = await self._get_own(user_id, city_id)
        self._move(city, "published")          # 409, если это не черновик
        city.description = data.description
        city.route = data.route
        city.lat = data.lat
        city.lon = data.lon
        city.published_at = datetime.now(timezone.utc)
        await self.db.commit()
        return CityOut.from_city(city)

    # ---------- DELETE (soft) ----------
    async def delete(self, user_id: int, city_id: int) -> None:
        city = await self._get_own(user_id, city_id)
        self._move(city, "deleted")
        await self.db.commit()

    # ---------- POST like ----------
    async def set_like(self, user_id: int, city_id: int, like: int) -> LikeOut:
        city = await self._get_visible(city_id)
        if city.status != "published":
            raise HTTPException(409, "Лайкать можно только опубликованные услуги")
        if like == 1:
            await self.likes.add(user_id, city_id)
        else:
            await self.likes.remove(user_id, city_id)
        await self.db.commit()
        count = await self.likes.count_for_city(city_id)
        return LikeOut(city_id=city_id, like=like, likes_count=count)
