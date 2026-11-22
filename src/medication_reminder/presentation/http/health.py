from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from medication_reminder.shared.config import Settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings: Annotated[Settings, "Application settings"] = request.app.state.settings
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.environment,
    )


@router.get("/ready", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse:
    settings: Annotated[Settings, "Application settings"] = request.app.state.settings
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    redis: Redis = request.app.state.redis
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        if not await redis.ping():
            raise RuntimeError("Redis ping failed")
    except Exception as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Dependencies are unavailable",
        ) from error
    return HealthResponse(
        status="ready",
        service=settings.app_name,
        environment=settings.environment,
    )
