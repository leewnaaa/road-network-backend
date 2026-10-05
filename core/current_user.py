from functools import lru_cache

CURRENT_USER_ID = 1


@lru_cache(maxsize=1)
def get_current_user_id() -> int:
    """Singleton: во всех методах текущий пользователь берётся только отсюда.
    В 4-й лабе заменится на получение пользователя из токена."""
    return CURRENT_USER_ID
