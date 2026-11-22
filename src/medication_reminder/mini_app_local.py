from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.gzip import GZipMiddleware

from medication_reminder.presentation.http.mini_app import router as mini_app_router
from medication_reminder.shared.config import Settings, get_settings
from medication_reminder.shared.database import create_database_engine, create_session_factory


def create_local_mini_app(settings: Settings | None = None) -> FastAPI:
    """Create the narrow local-tunnel surface used during Mini App development."""
    application_settings = settings or get_settings()
    engine = create_database_engine(
        application_settings.database_url,
        echo=application_settings.debug,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    application = FastAPI(
        title=f"{application_settings.app_name} Mini App",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    application.state.settings = application_settings
    application.state.session_factory = create_session_factory(engine)
    application.add_middleware(GZipMiddleware, minimum_size=500)
    application.include_router(mini_app_router)
    return application


app = create_local_mini_app()
