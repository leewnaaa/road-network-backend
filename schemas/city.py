from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.media import media_url
from models.city import City


class CityPublishIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    description: str = Field(min_length=1, max_length=500)
    route: str = Field(min_length=1, max_length=100)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class LikeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    like: Literal[0, 1]



class CityOut(BaseModel):
    id: int
    name: str
    description: str | None
    route: str | None
    lat: float | None
    lon: float | None
    status: str
    image_url: str | None
    video_url: str | None

    @classmethod
    def from_city(cls, city: City) -> "CityOut":
        return cls(
            id=city.id,
            name=city.name,
            description=city.description,
            route=city.route,
            lat=city.lat,
            lon=city.lon,
            status=city.status,
            image_url=media_url(city.image_url),
            video_url=media_url(city.video_url),
        )


class CityCardOut(BaseModel):
    id: int
    name: str
    description: str | None
    route: str | None
    lat: float | None
    lon: float | None
    image_url: str | None
    video_url: str | None
    likes_count: int
    is_mine: Literal[0, 1]   # 1, если создатель услуги = текущий пользователь

    @classmethod
    def from_city(cls, city: City, likes_count: int, current_user_id: int, **extra):
        return cls(
            id=city.id,
            name=city.name,
            description=city.description,
            route=city.route,
            lat=city.lat,
            lon=city.lon,
            image_url=media_url(city.image_url),
            video_url=media_url(city.video_url),
            likes_count=likes_count,
            is_mine=int(city.creator_id == current_user_id),
            **extra,
        )


class CityFeedOut(CityCardOut):
    liked_by_me: Literal[0, 1]


class LikeOut(BaseModel):
    city_id: int
    like: Literal[0, 1]
    likes_count: int
