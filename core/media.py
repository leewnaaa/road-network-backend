from core.config import settings


def media_url(filename: str | None) -> str | None:
    if not filename:
        return None
    return f"{settings.MINIO_PUBLIC_URL}/{settings.MINIO_BUCKET}/{filename}"
