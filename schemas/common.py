from pydantic import BaseModel, Field


class ErrorOut(BaseModel):
    """Формат ошибки FastAPI: HTTPException(status, detail)."""

    detail: str = Field(examples=["Требуется авторизация"])
