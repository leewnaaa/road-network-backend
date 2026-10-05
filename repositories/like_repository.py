from sqlalchemy import select, func, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.like import Like


class LikeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def count_for_city(self, city_id: int) -> int:
        result = await self.db.execute(
            select(func.count(Like.id)).where(Like.city_id == city_id)
        )
        return result.scalar_one()

    async def count_map(self, city_ids: list[int]) -> dict[int, int]:
        """{city_id: количество лайков} одним запросом, COUNT + GROUP BY в БД."""
        if not city_ids:
            return {}
        result = await self.db.execute(
            select(Like.city_id, func.count(Like.id))
            .where(Like.city_id.in_(city_ids))
            .group_by(Like.city_id)
        )
        return {city_id: count for city_id, count in result.all()}

    async def is_liked(self, user_id: int, city_id: int) -> bool:
        result = await self.db.execute(
            select(Like.id).where(Like.user_id == user_id, Like.city_id == city_id)
        )
        return result.first() is not None

    async def add(self, user_id: int, city_id: int) -> None:
        """Идемпотентно: повторный лайк не создаёт дубль и не падает."""
        await self.db.execute(
            pg_insert(Like)
            .values(user_id=user_id, city_id=city_id)
            .on_conflict_do_nothing(constraint="uq_likes_user_city")
        )

    async def remove(self, user_id: int, city_id: int) -> None:
        await self.db.execute(
            delete(Like).where(Like.user_id == user_id, Like.city_id == city_id)
        )
