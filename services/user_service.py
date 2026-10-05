import asyncio

import bcrypt
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from repositories.user_repository import UserRepository
from schemas.user import MessageOut, UserOut, UserRegisterIn


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

    # --- заглушки под 4-ю лабораторную ---
    async def login_stub(self) -> MessageOut:
        return MessageOut(message="Заглушка: аутентификация будет реализована в лабораторной 4")

    async def logout_stub(self) -> MessageOut:
        return MessageOut(message="Заглушка: деавторизация будет реализована в лабораторной 4")
