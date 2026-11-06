from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=settings.database_pool_min_size,
            max_size=settings.database_pool_max_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )
        _pool.open(wait=False)
    return _pool


@contextmanager
def connection(timeout: float = 5) -> Iterator[Any]:
    with get_pool().connection(timeout=timeout) as conn:
        yield conn


def database_available() -> bool:
    try:
        with connection(timeout=1) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() is not None
    except Exception:
        return False


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
