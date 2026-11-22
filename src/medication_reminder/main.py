from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis
from starlette.middleware.gzip import GZipMiddleware

from medication_reminder import __version__
from medication_reminder.presentation.http.health import router as health_router
from medication_reminder.presentation.http.mini_app import router as mini_app_router
from medication_reminder.shared.config import Settings, get_settings
from medication_reminder.shared.database import create_database_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    application_settings = settings or get_settings()
    engine = create_database_engine(
        application_settings.database_url,
        echo=application_settings.debug,
    )
    redis = Redis.from_url(application_settings.redis_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await redis.aclose()
        await engine.dispose()

    application = FastAPI(
        title=application_settings.app_name,
        version=__version__,
        debug=application_settings.debug,
        lifespan=lifespan,
    )
    application.state.settings = application_settings
    application.state.database_engine = engine
    application.state.session_factory = create_session_factory(engine)
    application.state.redis = redis
    application.add_middleware(GZipMiddleware, minimum_size=500)
    application.include_router(health_router)
    application.include_router(mini_app_router)

    return application


app = create_app()
