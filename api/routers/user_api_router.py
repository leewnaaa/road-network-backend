from fastapi import APIRouter, Depends, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.current_user import get_current_session
from core.redis_client import get_redis
from db.session import get_db
from schemas.common import ErrorOut
from schemas.user import MessageOut, UserLoginIn, UserOut, UserRegisterIn
from services.session_service import SessionData, SessionService
from services.user_service import UserService

router = APIRouter(prefix="/api/users", tags=["Пользователи"])


def get_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


def get_sessions(redis: Redis = Depends(get_redis)) -> SessionService:
    return SessionService(redis)


@router.post(
    "",
    response_model=UserOut,
    status_code=201,
    summary="Регистрация",
    description="Создаёт пользователя. Пароль хранится в виде bcrypt-хэша. Доступно гостю.",
    responses={409: {"model": ErrorOut, "description": "Логин уже занят"}},
)
async def register(data: UserRegisterIn, service: UserService = Depends(get_service)):
    return await service.register(data)


@router.post(
    "/login",
    response_model=UserOut,
    summary="Аутентификация",
    description=(
        "Проверяет логин и пароль, создаёт сессию в Redis и устанавливает "
        f"HttpOnly-куку `{settings.SESSION_COOKIE_NAME}`. Дальше браузер (в том числе Swagger) "
        "присылает её автоматически; в Insomnia/Postman значение куки копируется вручную."
    ),
    responses={401: {"model": ErrorOut, "description": "Неверный логин или пароль"}},
)
async def login(
    data: UserLoginIn,
    response: Response,
    service: UserService = Depends(get_service),
    sessions: SessionService = Depends(get_sessions),
):
    user = await service.authenticate(data)
    session_id = await sessions.create(user.id, user.username)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        max_age=settings.SESSION_TTL_SECONDS,
        httponly=True,                 # недоступна из JavaScript (защита от кражи через XSS)
        samesite="lax",                # не отправляется со сторонних сайтов при POST (защита от CSRF)
        secure=settings.COOKIE_SECURE,
        path="/",
    )
    return UserOut.model_validate(user)


@router.post(
    "/logout",
    response_model=MessageOut,
    summary="Деавторизация",
    description="Удаляет сессию из Redis и стирает куку. Метод авторизованного пользователя.",
    responses={401: {"model": ErrorOut, "description": "Не авторизован"}},
)
async def logout(
    response: Response,
    session: SessionData = Depends(get_current_session),
    sessions: SessionService = Depends(get_sessions),
):
    await sessions.delete(session.session_id)
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    return MessageOut(message="Вы вышли из системы")


@router.get(
    "/me",
    response_model=UserOut,
    summary="Текущий пользователь",
    description="Возвращает пользователя по сессии. Нужен фронтенду, чтобы понять, вошёл ли пользователь.",
    responses={401: {"model": ErrorOut, "description": "Не авторизован"}},
)
async def me(session: SessionData = Depends(get_current_session)):
    return UserOut(id=session.user_id, username=session.username)
