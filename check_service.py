import asyncio
from io import BytesIO

from starlette.datastructures import Headers, UploadFile

from db.session import async_session_maker
from schemas.city import CityPublishIn
from services.city_api_service import CityApiService


def up(content_type: str) -> UploadFile:
    return UploadFile(file=BytesIO(b"x" * 100), filename="f",
                      headers=Headers({"content-type": content_type}))


async def expect(label, coro):
    try:
        await coro
        print(label, "-> НЕ УПАЛО (ошибка!)")
    except Exception as e:
        print(label, "->", getattr(e, "status_code", e), getattr(e, "detail", ""))


async def main():
    data = CityPublishIn(description="Описание", route="М-4", lat=55.0, lon=37.0)
    async with async_session_maker() as db:
        s = CityApiService(db)

        c = await s.create_draft(1, "Тестоград", up("image/jpeg"), up("video/mp4"))
        print("создан:", c)
        print("черновик:", await s.get_draft(1))
        await expect("второй черновик", s.create_draft(1, "Второй", up("image/jpeg"), up("video/mp4")))

        await expect("лайк черновика", s.set_like(1, c.id, 1))
        print("публикация:", (await s.publish(1, c.id, data)).status)
        await expect("повторная публикация", s.publish(1, c.id, data))

        print("лайк 1:", await s.set_like(1, c.id, 1))
        print("лайк 1 ещё раз:", await s.set_like(1, c.id, 1))
        print("лента:", await s.get_feed(1, None, False))
        print("лента next:", (await s.get_feed(1, c.id, True)).id)
        print("список:", len(await s.list_published(1, "", "", None)))
        print("список lat_max=10:", len(await s.list_published(1, "", "", 10)))
        print("лайк 0:", await s.set_like(1, c.id, 0))

        await expect("чужой пользователь удаляет", s.delete(2, c.id))
        await s.delete(1, c.id)
        print("удалено")
        await expect("повторное удаление", s.delete(1, c.id))
        await expect("лента удалённой", s.get_feed(1, c.id, False))


asyncio.run(main())
