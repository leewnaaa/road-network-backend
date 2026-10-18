"""Смоук-тест авторизации: SQLite вместо PostgreSQL, fakeredis вместо Redis."""
import asyncio
import os
import sys
from pathlib import Path

for k, v in dict(DB_HOST="x", DB_PORT="1", DB_USER="x", DB_PASSWORD="x", DB_NAME="x",
                 MINIO_ENDPOINT="x:1", MINIO_ACCESS_KEY="x", MINIO_SECRET_KEY="x",
                 MINIO_BUCKET="b", MINIO_PUBLIC_URL="http://m").items():
    os.environ.setdefault(k, v)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.base import Base
import models.city, models.like, models.user  # noqa: F401  (регистрация таблиц)
from db.session import get_db
from core.redis_client import get_redis
from models.city import City
from main import app

DB_FILE = Path(__file__).with_name("test.sqlite3")


@pytest.fixture()
def env():
    DB_FILE.unlink(missing_ok=True)
    engine = create_async_engine(f"sqlite+aiosqlite:///{DB_FILE}")
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def init():
        async with engine.begin() as c:
            await c.run_sync(Base.metadata.create_all)
    asyncio.run(init())

    async def _db():
        async with maker() as s:
            yield s

    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_redis] = lambda: redis
    yield TestClient(app), maker, redis
    app.dependency_overrides.clear()
    DB_FILE.unlink(missing_ok=True)


def add_city(maker, creator_id, status="draft", **kw):
    async def go():
        async with maker() as s:
            s.add(City(name="Ростов", status=status, creator_id=creator_id, **kw))
            await s.commit()
    asyncio.run(go())


def register_login(client, name):
    assert client.post("/api/users", json={"username": name, "password": "secret123"}).status_code == 201
    r = client.post("/api/users/login", json={"username": name, "password": "secret123"})
    assert r.status_code == 200
    return r


def test_guest_read_ok_and_write_denied(env):
    client, _, _ = env
    assert client.get("/api/cities").status_code == 200
    assert client.get("/api/cities/feed").status_code == 404        # лент пока нет, но не 401
    for method, url, kw in [
        ("get", "/api/users/me", {}),
        ("get", "/api/cities/draft", {}),
        ("put", "/api/cities/1/publish", dict(json={"description": "d", "route": "r", "lat": 1, "lon": 2})),
        ("delete", "/api/cities/1", {}),
        ("post", "/api/cities/1/like", dict(json={"like": 1})),
        ("post", "/api/users/logout", {}),
    ]:
        assert getattr(client, method)(url, **kw).status_code == 401, url


def test_login_sets_cookie_and_redis_session(env):
    client, _, redis = env
    r = register_login(client, "alice")
    set_cookie = r.headers["set-cookie"]
    assert "session_id=" in set_cookie and "HttpOnly" in set_cookie and "SameSite=lax" in set_cookie
    sid = client.cookies.get("session_id")
    data = asyncio.run(redis.hgetall(f"session:{sid}"))
    assert data["username"] == "alice"
    assert asyncio.run(redis.ttl(f"session:{sid}")) > 0
    assert client.get("/api/users/me").json()["username"] == "alice"


def test_wrong_password_and_unknown_user(env):
    client, _, _ = env
    client.post("/api/users", json={"username": "bob", "password": "secret123"})
    assert client.post("/api/users/login", json={"username": "bob", "password": "bad"}).status_code == 401
    assert client.post("/api/users/login", json={"username": "nobody", "password": "bad"}).status_code == 401
    assert "session_id" not in client.cookies


def test_forged_cookie_rejected(env):
    client, _, _ = env
    client.cookies.set("session_id", "forged")
    assert client.get("/api/users/me").status_code == 401


def test_publish_guest_401_owner_ok_stranger_403(env):
    client, maker, _ = env
    register_login(client, "owner")                 # id = 1
    add_city(maker, creator_id=1)
    body = {"description": "Город", "route": "М-4", "lat": 47.2, "lon": 39.7}

    guest = TestClient(app)
    assert guest.put("/api/cities/1/publish", json=body).status_code == 401

    r = client.put("/api/cities/1/publish", json=body)
    assert r.status_code == 200
    assert r.json()["status"] == "published" and r.json()["route"] == "М-4"

    # опубликованное видит гость, is_mine = 0
    lst = guest.get("/api/cities").json()
    assert len(lst) == 1 and lst[0]["is_mine"] == 0
    assert client.get("/api/cities").json()[0]["is_mine"] == 1
    assert guest.get("/api/cities/feed").json()["liked_by_me"] == 0

    add_city(maker, creator_id=1)                   # второй черновик владельца
    other = TestClient(app)
    register_login(other, "stranger")
    assert other.put("/api/cities/2/publish", json=body).status_code == 403


def test_logout_kills_session(env):
    client, _, redis = env
    register_login(client, "carol")
    sid = client.cookies.get("session_id")
    assert client.post("/api/users/logout").status_code == 200
    assert asyncio.run(redis.exists(f"session:{sid}")) == 0
    client.cookies.set("session_id", sid)           # старая кука больше не работает
    assert client.get("/api/users/me").status_code == 401


def test_openapi_locks_only_on_creator_methods(env):
    client, _, _ = env
    spec = client.get("/openapi.json").json()
    secured = {(m.upper(), p) for p, ops in spec["paths"].items() for m, op in ops.items() if op.get("security")}
    open_ = {(m.upper(), p) for p, ops in spec["paths"].items() for m, op in ops.items() if not op.get("security")}
    assert ("GET", "/api/cities") in open_ and ("GET", "/api/cities/feed") in open_
    assert ("GET", "/api/cities/feed/{city_id}") in open_
    assert ("POST", "/api/users") in open_ and ("POST", "/api/users/login") in open_
    assert {("PUT", "/api/cities/{city_id}/publish"), ("POST", "/api/cities"), ("GET", "/api/cities/draft"),
            ("DELETE", "/api/cities/{city_id}"), ("POST", "/api/cities/{city_id}/like"),
            ("POST", "/api/users/logout"), ("GET", "/api/users/me")} <= secured
    assert "/" not in spec["paths"] and "/cities" not in spec["paths"]   # HTML скрыт
