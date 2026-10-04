from sqlalchemy import select, func
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
        """{city_id: количество лайков} одним запросом — COUNT()+GROUP BY в самой БД, без ручного +1 в Python."""
        if not city_ids:
            return {}
        result = await self.db.execute(
            select(Like.city_id, func.count(Like.id))
            .where(Like.city_id.in_(city_ids))
            .group_by(Like.city_id)
        )
        return {city_id: count for city_id, count in result.all()}
