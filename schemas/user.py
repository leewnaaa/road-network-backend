from pydantic import BaseModel, ConfigDict, Field


from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=72)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Пароль длиннее 72 байт (кириллица занимает по 2 байта)")
        return v


class UserLoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class MessageOut(BaseModel):
    message: str
