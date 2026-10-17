# ДОРСЕТЬ — Дорожная сеть (backend, лабораторная 3)

Веб-сервис на FastAPI для SPA: города дорожной сети с фото и видео, лента в стиле reels, плитка с фильтром, лайки.
Авторизации пока нет — текущий пользователь зафиксирован константой через функцию-singleton (в 4-й лабе заменится на пользователя из токена).

## Стек

FastAPI · SQLAlchemy 2 (async, ORM) · PostgreSQL 15 · Alembic · MinIO · Pydantic v2 · bcrypt

## Запуск

```bash
docker compose up -d          # PostgreSQL (15432), MinIO (9000/9001), Adminer (8081)
pip install -r requirements.txt
alembic upgrade head          # таблицы + пользователь с id=1
python main.py                # http://localhost:8000 , Swagger: /docs
```

Файл `.env`:

```env
DB_HOST=localhost
DB_PORT=15432
DB_USER=myuser
DB_PASSWORD=mypassword
DB_NAME=dorset_db

MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=cities
MINIO_PUBLIC_URL=http://localhost:9000
```

## Архитектура

Слои: **router** (HTTP) → **service** (бизнес-логика) → **repository** (запросы к БД через ORM) → **model** (таблица).

| Слой | Файлы |
|---|---|
| Роутеры (домены) | `api/routers/city_api_router.py`, `api/routers/user_api_router.py` |
| Сервисы | `services/city_api_service.py`, `services/user_service.py`, `services/storage_service.py` |
| Репозитории | `repositories/city_repository.py`, `like_repository.py`, `user_repository.py` |
| Модели | `models/city.py`, `models/like.py`, `models/user.py` |
| Схемы (сериализаторы) | `schemas/city.py`, `schemas/user.py` |
| Singleton | `core/current_user.py` (`get_current_user_id`), `core/minio_client.py` (`get_minio`) |

- Модели описывают таблицы БД. Схемы описывают, что клиент **может прислать** и что **получает**.
- Системные поля (`id`, `status`, `creator_id`, `created_at`, `published_at`) клиент менять не может: во входных схемах стоит `extra="forbid"` (лишнее поле → 422), а значения вычисляются на бэкенде.
- Текущий пользователь берётся только через `Depends(get_current_user_id)`.
- Файлы лежат в MinIO, в БД хранится только имя файла (`img_<uuid>.jpg`, `vid_<uuid>.mp4`, латиница, генерируется на сервере). Клиенту отдаётся полная ссылка `MINIO_PUBLIC_URL/MINIO_BUCKET/<имя>`.
- Записи в статусе `deleted` клиенту не передаются (404).

## Статусы услуги

```
draft ──► published ──► deleted
  └──────────────────────►┘
```

| Из | В | Метод |
|---|---|---|
| draft | published | `PUT /api/cities/{id}/publish` |
| draft | deleted | `DELETE /api/cities/{id}` |
| published | deleted | `DELETE /api/cities/{id}` |

Вернуть в черновик нельзя. Любой другой переход → `409`. Допустимые переходы заданы словарём `ALLOWED_TRANSITIONS` в `city_api_service.py`, а `CHECK`-ограничение в БД не даёт записать неизвестный статус.

## Таблицы БД

### users

| Поле | Тип | Ограничения | Описание |
|---|---|---|---|
| id | integer | PK | идентификатор |
| username | varchar(50) | NOT NULL, UNIQUE | логин |
| password | varchar(255) | NULL | хеш bcrypt (`$2b$...`), открытый пароль не хранится |

Пользователь с `id=1` создаётся миграцией — это текущий пользователь из singleton.

### cities

| Поле | Тип | Ограничения | Описание |
|---|---|---|---|
| id | integer | PK | идентификатор |
| name | varchar(100) | NOT NULL | название города |
| description | varchar(500) | NULL | описание (заполняется при публикации) |
| status | varchar(20) | NOT NULL, default `draft`, CHECK `draft/published/deleted` | статус |
| image_url | varchar(255) | NULL | имя файла фото в MinIO |
| video_url | varchar(255) | NULL | имя файла видео в MinIO |
| route | varchar(100) | NULL | дорога / регион (при публикации) |
| lat | double precision | NULL | широта (при публикации) |
| lon | double precision | NULL | долгота (при публикации) |
| creator_id | integer | NOT NULL, FK → users.id | создатель |
| created_at | timestamptz | default `now()` | дата создания |
| published_at | timestamptz | NULL | дата публикации |

### likes

| Поле | Тип | Ограничения | Описание |
|---|---|---|---|
| id | integer | PK | идентификатор |
| user_id | integer | NOT NULL, FK → users.id | кто лайкнул |
| city_id | integer | NOT NULL, FK → cities.id | какой город |

`UNIQUE (user_id, city_id)` — один лайк от пользователя на услугу. Лайк `1` вставляет строку (повтор безопасен, `ON CONFLICT DO NOTHING`), `0` удаляет.

Связи: `cities.creator_id → users.id`, `likes.user_id → users.id`, `likes.city_id → cities.id`.

## HTTP-методы

Все адреса начинаются с `/api`.

| № | Метод | URL | Описание | Успех |
|---|---|---|---|---|
| 1 | GET | `/api/cities` | список опубликованных с фильтрацией | 200 |
| 2 | GET | `/api/cities/feed?city_id=&next=` | лента: без параметров — самая новая; с `city_id` — эта услуга; с `city_id` и `next=true` — следующая | 200 |
| 3 | GET | `/api/cities/draft` | черновик текущего пользователя (id не нужен) | 200 |
| 4 | POST | `/api/cities` | создание черновика + фото и видео | 201 |
| 5 | PUT | `/api/cities/{city_id}/publish` | публикация (draft → published) | 200 |
| 6 | DELETE | `/api/cities/{city_id}` | мягкое удаление (только свои) | 204 |
| 7 | POST | `/api/cities/{city_id}/like` | лайк (1) / отмена лайка (0) | 200 |
| 8 | POST | `/api/users` | регистрация | 201 |
| 9 | POST | `/api/users/login` | аутентификация (заглушка для лабы 4) | 200 |
| 10 | POST | `/api/users/logout` | деавторизация (заглушка для лабы 4) | 200 |

Всего 10 методов: 7 в домене услуг (`/api/cities`) и 3 в домене пользователей (`/api/users`).

### 1. GET `/api/cities`

Query-параметры (все необязательные): `route` — точное совпадение дороги; `search` — подстрока в названии (без учёта регистра); `lat_max` — широта не больше значения. Сортировка по названию. Возвращает только опубликованные.

Элемент ответа:

```json
{
  "id": 9, "name": "Тестоград", "description": "Описание", "route": "М-4 «Дон»",
  "lat": 55.7, "lon": 37.6,
  "image_url": "http://localhost:9000/cities/img_....jpg",
  "video_url": "http://localhost:9000/cities/vid_....mp4",
  "likes_count": 3,
  "is_mine": 1
}
```

`is_mine`: 1, если создатель услуги совпадает с текущим пользователем, иначе 0.

### 2. GET `/api/cities/feed`

Один метод, два необязательных query-параметра: `city_id` и `next`.

- без параметров — самая новая опубликованная услуга;
- `?city_id=9` — эта услуга (если она опубликована);
- `?city_id=9&next=true` — следующая по порядку публикации (более старая); если дальше ничего нет, лента начинается заново с самой новой.

Ответ — как в п. 1 плюс `liked_by_me` (0/1). Ошибка `404`, если услуги нет, она не опубликована или удалена.

### 3. GET `/api/cities/draft`

Возвращает черновик текущего пользователя (не более одного). `404`, если черновика нет. Ответ: `id, name, description, route, lat, lon, status, image_url, video_url`.

### 4. POST `/api/cities`

`multipart/form-data`:

| Поле | Тип | Описание |
|---|---|---|
| name | text | название города |
| photo | file | jpeg / png / webp, до 5 МБ |
| video | file | mp4 / webm, до 50 МБ |

Файлы сохраняются в MinIO под сгенерированными латинскими именами, имена записываются в `image_url` и `video_url`. Статус `draft` и создатель выставляются на бэкенде. Ошибки: `409` — черновик уже есть, `400` — пустое название или пустой файл, `413` — файл слишком большой, `415` — недопустимый тип файла, `502` — MinIO недоступен. Если запись в БД не удалась, загруженные файлы удаляются.

### 5. PUT `/api/cities/{city_id}/publish`

```json
{ "description": "Описание", "route": "М-4 «Дон»", "lat": 55.7, "lon": 37.6 }
```

Все четыре поля обязательны, других полей быть не должно (`422`). Проставляет `status = published` и `published_at`. Ошибки: `403` — чужая услуга, `404` — нет или удалена, `409` — услуга не в статусе `draft`.

### 6. DELETE `/api/cities/{city_id}`

Мягкое удаление через ORM: `status = deleted`, файлы в MinIO остаются. Только услуги текущего пользователя. Ответ `204` без тела. Ошибки: `403`, `404`, `409`.

### 7. POST `/api/cities/{city_id}/like`

```json
{ "like": 1 }
```

`1` — поставить лайк, `0` — снять. Ответ: `{ "city_id": 9, "like": 1, "likes_count": 1 }`. Лайкать можно только опубликованные услуги (`409` иначе).

### 8. POST `/api/users`

```json
{ "username": "newuser", "password": "secret123" }
```

Логин 3–50 символов, пароль 6–72 **байта**. Пароль сохраняется как хеш bcrypt. Ответ: `{ "id": 5, "username": "newuser" }` — пароль в ответ не попадает. `409`, если логин занят.

### 9–10. POST `/api/users/login`, `/api/users/logout`

Заглушки: ничего не проверяют, возвращают `{ "message": "..." }`. Реализуются в лабораторной 4.

## Коды ошибок

| Код | Когда |
|---|---|
| 400 | пустое название или пустой файл |
| 403 | чужая услуга |
| 404 | услуга не найдена, удалена, черновика нет |
| 409 | недопустимый переход статуса, второй черновик, дубль логина, лайк неопубликованной |
| 413 | файл больше лимита |
| 415 | недопустимый тип файла |
| 422 | ошибка валидации (в т. ч. лишние/системные поля в теле) |
| 502 | MinIO недоступен |

## Диаграмма классов

Диаграмма классов лежит в `dorset_class_diagram.drawio` (открывается на https://app.diagrams.net).

## Миграции

```bash
alembic revision --autogenerate -m "описание"
alembic upgrade head
```

Папка `alembic/versions` хранится в git.
