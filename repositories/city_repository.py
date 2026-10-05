from sqlalchemy import select, text, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.city import City


class CityRepository:
    """Слой доступа к данным: только запросы к БД, никакой бизнес-логики."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, city_id: int) -> City | None:
        result = await self.db.execute(select(City).where(City.id == city_id))
        return result.scalar_one_or_none()

    async def get_published_filtered(
        self, route: str = "", search: str = "", lat_max: float | None = None
    ) -> list[City]:
        stmt = select(City).where(City.status == "published")
        if route:
            stmt = stmt.where(City.route == route)
        if search:
            stmt = stmt.where(City.name.ilike(f"%{search}%"))
        if lat_max is not None:
            stmt = stmt.where(City.lat <= lat_max)
        result = await self.db.execute(stmt.order_by(City.name))
        return result.scalars().all()

    async def get_draft(self, user_id: int) -> City | None:
        result = await self.db.execute(
            select(City)
            .where(City.creator_id == user_id, City.status == "draft")
            .order_by(City.id)
            .limit(1)
        )
        return result.scalars().first()

    async def get_newest_published(self) -> City | None:
        result = await self.db.execute(
            select(City)
            .where(City.status == "published")
            .order_by(City.published_at.desc(), City.id.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_older_published(self, current: City) -> City | None:
        """Следующая в ленте: опубликована раньше текущей. id с пропусками не мешают."""
        result = await self.db.execute(
            select(City)
            .where(
                City.status == "published",
                or_(
                    City.published_at < current.published_at,
                    and_(City.published_at == current.published_at, City.id < current.id),
                ),
            )
            .order_by(City.published_at.desc(), City.id.desc())
            .limit(1)
        )
        return result.scalars().first()

    # ---------- используется только старыми HTML-роутерами ----------
    async def get_next_published(self, after_id: int | None) -> City | None:
        if after_id is not None:
            current = await self.get_by_id(after_id)
            if current and current.published_at is not None:
                nxt = await self.get_older_published(current)
                if nxt:
                    return nxt
        return await self.get_newest_published()

    def add(self, city: City) -> None:
        self.db.add(city)

    async def soft_delete(self, city_id: int) -> None:
        await self.db.execute(
            text("UPDATE cities SET status = 'deleted' WHERE id = :id"),
            {"id": city_id},
        )

    async def commit(self) -> None:
        await self.db.commit()
