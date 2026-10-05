import asyncio
import os
import uuid
from typing import Literal

from fastapi import HTTPException, UploadFile
from minio.error import S3Error

from core.config import settings
from core.minio_client import get_minio

MediaKind = Literal["image", "video"]

RULES: dict[str, dict] = {
    "image": {
        "prefix": "img",
        "max_size": 5 * 1024 * 1024,
        "types": {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        },
    },
    "video": {
        "prefix": "vid",
        "max_size": 50 * 1024 * 1024,
        "types": {
            "video/mp4": ".mp4",
            "video/webm": ".webm",
        },
    },
}

from pathlib import Path

EXT_FALLBACK = {
    "image": {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"},
    "video": {".mp4": "video/mp4", ".webm": "video/webm"},
}


class StorageService:

    def __init__(self):
        self.client = get_minio()
        self.bucket = settings.MINIO_BUCKET

    async def upload(self, file: UploadFile, kind: MediaKind) -> str:
        rules = RULES[kind]

        content_type = (file.content_type or "").lower()
        if content_type in ("", "application/octet-stream"):
            suffix = Path(file.filename or "").suffix.lower()
            content_type = EXT_FALLBACK[kind].get(suffix, content_type)

        ext = rules["types"].get(content_type)
        if ext is None:
            allowed = ", ".join(rules["types"])
            raise HTTPException(415, f"Недопустимый тип файла ({kind}). Разрешено: {allowed}")

        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)

        if size == 0:
            raise HTTPException(400, f"Пустой файл ({kind})")
        if size > rules["max_size"]:
            raise HTTPException(413, f"Файл слишком большой ({kind}), максимум {rules['max_size'] // 1024 // 1024} МБ")

        filename = f"{rules['prefix']}_{uuid.uuid4().hex}{ext}"

        try:
            await asyncio.to_thread(
                self.client.put_object,
                self.bucket,
                filename,
                file.file,
                size,
                content_type=file.content_type,
            )
        except S3Error as e:
            raise HTTPException(502, f"Хранилище файлов недоступно: {e.code}")

        return filename

    async def delete(self, filename: str | None) -> None:
        if not filename:
            return
        try:
            await asyncio.to_thread(self.client.remove_object, self.bucket, filename)
        except S3Error:
            pass
