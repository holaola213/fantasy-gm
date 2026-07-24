from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.shared.database.session import check_database_connection

DatabaseHealthCheck = Callable[[], Awaitable[None]]

router = APIRouter(tags=["health"])


def get_database_health_check() -> DatabaseHealthCheck:
    return check_database_connection


@router.get("/health", status_code=status.HTTP_200_OK)
async def read_health(
    database_health_check: Annotated[
        DatabaseHealthCheck, Depends(get_database_health_check)
    ],
) -> dict[str, str]:
    try:
        await database_health_check()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc

    return {"status": "ok", "database": "connected"}
