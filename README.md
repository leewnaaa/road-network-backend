# ДОРСЕТЬ — Дорожная сеть (backend, лабораторная 4)

Веб-сервис на FastAPI для SPA: города дорожной сети с фото и видео, лента в стиле reels, плитка с фильтром, лайки.
В лабораторной 4 добавлены регистрация, аутентификация и деавторизация на серверных сессиях в Redis, разграничение прав гость / создатель и описание методов в Swagger.

## Стек

FastAPI · SQLAlchemy 2 (async, ORM) · PostgreSQL 15 · Alembic · MinIO · Redis 7 · Pydantic v2 · bcrypt

## Запуск

```bash
docker compose up -d          # PostgreSQL (15432), MinIO (9000/9001), Redis (6379), Adminer (8081)
pip install -r requirements.txt
alembic upgrade head          # таблицы users, cities, likes
python main.py                # http://127.0.0.1:8000 , Swagger: /docs
```

Новых таблиц и полей в лабораторной 4 нет: сессии хранятся в Redis, а не в PostgreSQL.

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

REDIS_HOST=localhost
REDIS_PORT=6379
SESSION_TTL_SECONDS=86400
```

## Архитектура

Слои: **router** (HTTP, проверка прав) → **service** (бизнес-логика) → **repository** (запросы к БД через ORM) → **model** (таблица). Redis и MinIO подключаются через отдельные клиенты.

| Слой | Файлы |
|---|---|
| Роутеры (домены) | `api/routers/city_api_router.py`, `api/routers/user_api_router.py` |
| Сервисы | `services/city_api_service.py`, `services/user_service.py`, `services/session_service.py`, `services/storage_service.py` |
| Репозитории | `repositories/city_repository.py`, `like_repository.py`, `user_repository.py` |
| Модели | `models/city.py`, `models/like.py`, `models/user.py` |
| Схемы (сериализаторы) | `schemas/city.py`, `schemas/user.py` |
| Зависимости доступа | `get_current_user_id`, `get_optional_user_id` |
| Клиенты | `core/redis_client.py`, `core/minio_client.py` (`get_minio`) |

- Модели описывают таблицы БД. Схемы описывают, что клиент **может прислать** и что **получает**.
- Системные поля (`id`, `status`, `creator_id`, `created_at`, `published_at`) клиент менять не может: во входных схемах стоит `extra="forbid"` (лишнее поле → 422), а значения вычисляются на бэкенде.
- Создатель услуги (`creator_id`) подставляется автоматически из сессии, клиент его не передаёт.
- Файлы лежат в MinIO, в БД хранится только имя файла (`img_<uuid>.jpg`, `vid_<uuid>.mp4`, латиница, генерируется на сервере). Клиенту отдаётся полная ссылка `MINIO_PUBLIC_URL/MINIO_BUCKET/<имя>`.
- Записи в статусе `deleted` клиенту не передаются (404).

## Аутентификация и авторизация

### Как работает вход

1. `POST /api/users/login` проверяет логин и пароль (bcrypt). Для неизвестного логина и неверного пароля возвращается одинаковая ошибка `401`, чтобы нельзя было перебирать логины.
2. `SessionService.create` генерирует случайный идентификатор сессии (256 бит) и сохраняет в Redis хэш `session:<id>` с полями `user_id` и `username`. Время жизни ключа — 24 часа (`SESSION_TTL_SECONDS`), по истечении Redis удаляет его сам.
3. Идентификатор отправляется клиенту в куке `session_id` с флагами `HttpOnly` и `SameSite=Lax`. JavaScript в браузере эту куку прочитать не может.
4. При каждом запросе роутер читает куку, `SessionService.get` ищет сессию в Redis и определяет пользователя.
5. `POST /api/users/logout` удаляет ключ из Redis и стирает куку, поэтому старая кука перестаёт работать сразу (`401`).

### Роли

| Роль | Кто | Что доступно |
|---|---|---|
| Гость | запрос без куки или с недействительной сессией | регистрация, вход, чтение списка и ленты |
| Создатель | запрос с действительной кукой `session_id` | всё, что у гостя, плюс создание, публикация и удаление своих услуг, лайки, выход |

Права проверяют зависимости FastAPI:

- `get_optional_user_id` — для публичных методов чтения. Гость получает данные, поле `is_mine` для него равно `0`, `liked_by_me` равно `0`.
- `get_current_user_id` — для методов создателя. Нет куки или сессия истекла → `401`. Попытка изменить чужую услугу → `403`.

### Swagger

Документация доступна по адресу `/docs`. У методов создателя отображается замок: в OpenAPI объявлена схема безопасности `apiKey` в куке `session_id`. У публичных методов замка нет.

Как проверить в Swagger (лучше в окне инкогнито):

1. `POST /api/users` — зарегистрировать пользователя.
2. `POST /api/users/login` — выполнить вход. В ответе `200` и заголовок `set-cookie: session_id=…; HttpOnly; SameSite=lax`.
3. Методы создателя теперь работают: браузер сам отправляет куку. Кнопка **Authorize** для схемы «apiKey in cookie» куку не подставляет (браузеры запрещают задавать её из страницы), поэтому достаточно выполнить вход методом `login`.

Для Postman и Insomnia добавьте заголовок `Cookie: session_id=<значение>`. Значение берётся из DevTools → Application → Cookies или из ответа метода `login`.

### Просмотр сессий в Redis

```bash
docker exec -it dorset-redis redis-cli
keys *                          # session:<id>
HGETALL session:<id>            # user_id, username
TTL session:<id>                # секунды до истечения (около 86400)
```

Список логинов по активным сессиям:

```bash
docker exec -it dorset-redis redis-cli EVAL "local r={} for _,k in ipairs(redis.call('KEYS','session:*')) do r[#r+1]=k..' -> '..redis.call('HGET',k,'username') end return r" 0
```

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

### cities

| Поле | Тип | Ограничения | Описание |
|---|---|---|---|
| id | integer | PK | идентификатор |
| name | varchar(100) | NOT NULL | название города |
| description | varchar(500) | NULL | описание (заполняется при публикации) |
| status | varchar(20) | NOT NULL, default `draft`, CHECK `draft/published/deleted` | статус |
| image_url | varchar(255) | NULL | имя файла фото в MinIO |
| video_url | varchar(255) | NULL | имя файла видео в MinIO |
| lat | double precision | NULL | широта (при публикации) |
| lon | double precision | NULL | долгота (при публикации) |
| creator_id | integer | NOT NULL, FK → users.id | создатель (из сессии) |
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

### Хранилище сессий (Redis)

| Ключ | Тип | Поля | Время жизни |
|---|---|---|---|
| `session:<id>` | hash | `user_id`, `username` | 24 часа |

## HTTP-методы

Все адреса начинаются с `/api`. Колонка «Доступ»: **Г** — гость, **С** — создатель (нужна кука `session_id`).

| № | Метод | URL | Описание | Доступ | Успех |
|---|---|---|---|---|---|
| 1 | GET | `/api/cities` | список опубликованных с фильтром по широте (`lat_max`) | Г, С | 200 |
| 2 | GET | `/api/cities/feed?city_id=&next=` | лента: без параметров — самая новая; с `city_id` — эта услуга; с `city_id` и `next=true` — следующая | Г, С | 200 |
| 3 | GET | `/api/cities/draft` | черновик текущего пользователя (id не нужен) | С | 200 |
| 4 | POST | `/api/cities` | создание черновика + фото и видео | С | 201 |
| 5 | PUT | `/api/cities/{city_id}/publish` | публикация (draft → published) | С (свои) | 200 |
| 6 | DELETE | `/api/cities/{city_id}` | мягкое удаление (только свои) | С (свои) | 204 |
| 7 | POST | `/api/cities/{city_id}/like` | лайк (1) / отмена лайка (0) | С | 200 |
| 8 | POST | `/api/users` | регистрация | Г | 201 |
| 9 | POST | `/api/users/login` | аутентификация, создание сессии и куки | Г | 200 |
| 10 | POST | `/api/users/logout` | деавторизация, удаление сессии | С | 200 |

Всего 10 методов: 7 в домене услуг (`/api/cities`) и 3 в домене пользователей (`/api/users`).

### 1. GET `/api/cities`

Единственный фильтр — необязательный query-параметр `lat_max`: возвращаются услуги, у которых широта не больше заданного значения. Без параметра возвращаются все опубликованные. Сортировка по названию. Возвращает только опубликованные, независимо от того, кто их создал. Метод публичный: работает и без куки.

Элемент ответа:

```json
{
  "id": 9, "name": "Тестоград", "description": "Описание",
  "lat": 55.7, "lon": 37.6,
  "image_url": "http://localhost:9000/cities/img_....jpg",
  "video_url": "http://localhost:9000/cities/vid_....mp4",
  "likes_count": 3,
  "is_mine": 1
}
```

`is_mine`: 1, если создатель услуги совпадает с пользователем из сессии, иначе 0 (для гостя всегда 0).

### 2. GET `/api/cities/feed`

Один метод, два необязательных query-параметра: `city_id` и `next`. Метод публичный.

- без параметров — самая новая опубликованная услуга;
- `?city_id=9` — эта услуга (если она опубликована);
- `?city_id=9&next=true` — следующая по порядку публикации (более старая); если дальше ничего нет, лента начинается заново с самой новой.

Ответ — как в п. 1 плюс `liked_by_me` (0/1; для гостя всегда 0). Ошибка `404`, если услуги нет, она не опубликована или удалена.

### 3. GET `/api/cities/draft`

Возвращает черновик текущего пользователя (не более одного). Ответ: `id, name, description, lat, lon, status, image_url, video_url`. Ошибки: `401` — нет куки, `404` — черновика нет.

### 4. POST `/api/cities`

`multipart/form-data`:

| Поле | Тип | Описание |
|---|---|---|
| name | text | название города |
| photo | file | jpeg / png / webp, до 5 МБ |
| video | file | mp4 / webm, до 50 МБ |

Файлы сохраняются в MinIO под сгенерированными латинскими именами, имена записываются в `image_url` и `video_url`. Статус `draft` и создатель (из сессии) выставляются на бэкенде. Ошибки: `401` — нет куки, `409` — черновик уже есть, `400` — пустое название или пустой файл, `413` — файл слишком большой, `415` — недопустимый тип файла, `502` — MinIO недоступен. Если запись в БД не удалась, загруженные файлы удаляются.

### 5. PUT `/api/cities/{city_id}/publish`

```json
{ "description": "Описание", "lat": 55.7, "lon": 37.6 }
```

Все три поля обязательны, других полей быть не должно (`422`). Проставляет `status = published` и `published_at`. Ошибки: `401` — нет куки, `403` — чужая услуга, `404` — нет или удалена, `409` — услуга не в статусе `draft`.

### 6. DELETE `/api/cities/{city_id}`

Мягкое удаление через ORM: `status = deleted`, файлы в MinIO остаются. Только услуги текущего пользователя. Ответ `204` без тела. Ошибки: `401`, `403`, `404`, `409`.

### 7. POST `/api/cities/{city_id}/like`

```json
{ "like": 1 }
```

`1` — поставить лайк, `0` — снять. Ответ: `{ "city_id": 9, "like": 1, "likes_count": 1 }`. Лайкать можно только опубликованные услуги (`409` иначе). Ошибки: `401` — нет куки, `404` — услуга не найдена.

### 8. POST `/api/users`

```json
{ "username": "newuser", "password": "secret123" }
```

Логин 3–50 символов, пароль 6–72 **байта**. Пароль сохраняется как хеш bcrypt. Ответ: `{ "id": 5, "username": "newuser" }` — пароль в ответ не попадает. Ошибки: `409` — логин занят, `422` — ошибка валидации.

### 9. POST `/api/users/login`

```json
{ "username": "newuser", "password": "secret123" }
```

Ответ `200`: `{ "id": 5, "username": "newuser" }` и заголовок `Set-Cookie: session_id=<id>; HttpOnly; SameSite=Lax`. Ошибка `401` — неверный логин или пароль (одинаковый ответ в обоих случаях).

### 10. POST `/api/users/logout`

Требует куку. Удаляет сессию из Redis и стирает куку. Ответ: `{ "message": "..." }`. Ошибка `401` — нет куки или сессия недействительна.

## Коды ошибок

| Код | Когда |
|---|---|
| 400 | пустое название или пустой файл |
| 401 | нет куки `session_id`, сессия истекла или удалена; неверный логин или пароль |
| 403 | чужая услуга |
| 404 | услуга не найдена, удалена, черновика нет |
| 409 | недопустимый переход статуса, второй черновик, дубль логина, лайк неопубликованной |
| 413 | файл больше лимита |
| 415 | недопустимый тип файла |
| 422 | ошибка валидации (в т. ч. лишние/системные поля в теле) |
| 502 | MinIO недоступен |

Различие между `401` и `403`: `401` — система не знает, кто вы (нужно войти); `403` — вы известны, но действие запрещено (услуга принадлежит другому создателю).

## Документация

Диаграммы лежат в `docs/diagrams/`: диаграмма классов (`classes.puml`, `classes.png`), ER-диаграмма (`er.puml`, `er.png`) и диаграмма последовательности HTTP-запросов (`sequence.puml`, `sequence.png`). Исходники `.puml` открываются в PlantUML. Расчётно-пояснительная записка и техническое задание — в `docs/`.

## Миграции

```bash
alembic revision --autogenerate -m "описание"
alembic upgrade head
```

Папка `alembic/versions` хранится в git.
