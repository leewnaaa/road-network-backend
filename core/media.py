from core.config import settings


def media_url(filename: str | None) -> str | None:
    """Публичная ссылка на файл в MinIO.

    В БД новые услуги хранят только имя объекта (image_xxx.jpg), а записи, добавленные
    вручную в прошлых лабораторных, — уже готовую ссылку. Готовую ссылку не дополняем,
    иначе получится http://localhost:9000/cities/http://localhost:9000/cities/...
    """
    if not filename:
        return None
    if filename.startswith(("http://", "https://", "/")):
        return filename
    return f"{settings.MINIO_PUBLIC_URL}/{settings.MINIO_BUCKET}/{filename}"
