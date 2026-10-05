from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from schemas.user import MessageOut, UserLoginIn, UserOut, UserRegisterIn
from services.user_service import UserService

router = APIRouter(prefix="/api/users", tags=["Пользователи"])


def get_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


@router.post("", response_model=UserOut, status_code=201, summary="Регистрация")
async def register(data: UserRegisterIn, service: UserService = Depends(get_service)):
    return await service.register(data)


@router.post("/login", response_model=MessageOut, summary="Аутентификация (заглушка для лабы 4)")
async def login(data: UserLoginIn, service: UserService = Depends(get_service)):
    return await service.login_stub()


@router.post("/logout", response_model=MessageOut, summary="Деавторизация (заглушка для лабы 4)")
async def logout(service: UserService = Depends(get_service)):
    return await service.logout_stub()
