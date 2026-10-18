import asyncio

import bcrypt
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from repositories.user_repository import UserRepository
from schemas.user import UserLoginIn, UserOut, UserRegisterIn


# Хэш несуществующего пароля: bcrypt выполняется даже для неизвестного логина
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt()).decode("utf-8")


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)

    async def register(self, data: UserRegisterIn) -> UserOut:
        if await self.users.get_by_username(data.username):
            raise HTTPException(409, "Пользователь с таким логином уже существует")

        hashed = await asyncio.to_thread(
            bcrypt.hashpw, data.password.encode("utf-8"), bcrypt.gensalt()
        )
        user = User(username=data.username, password=hashed.decode("utf-8"))
        self.users.add(user)
        try:
            await self.db.commit()
        except IntegrityError:          # два запроса с одним логином одновременно
            await self.db.rollback()
            raise HTTPException(409, "Пользователь с таким логином уже существует")
        return UserOut.model_validate(user)

    async def authenticate(self, data: UserLoginIn) -> User:
        """Проверка логина/пароля. Одинаковая ошибка для неизвестного логина и неверного пароля."""
        user = await self.users.get_by_username(data.username)
        hashed = user.password if user and user.password else _DUMMY_HASH   # выравниваем время ответа
        ok = await asyncio.to_thread(
            bcrypt.checkpw, data.password.encode("utf-8"), hashed.encode("utf-8")
        )
        if user is None or not user.password or not ok:
            raise HTTPException(401, "Неверный логин или пароль")
        return user
