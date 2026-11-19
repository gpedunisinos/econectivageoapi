import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.biodiversity import router as biodiversity_router
from app.api.deter import router as deter_router
from app.api.routes import router
from app.config import get_settings
from app.database import close_pool
from app.services.deter import sync_snapshot


@asynccontextmanager
async def lifespan(_: FastAPI):
    async def refresh():
        while True:
            try:
                await asyncio.to_thread(sync_snapshot)
            except Exception:
                logging.getLogger(__name__).exception(
                    "DETER refresh failed; last snapshot retained"
                )
            await asyncio.sleep(3600)

    task = asyncio.create_task(refresh())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Consulta contexto socioambiental por coordenada e publica camadas "
            "geográficas nacionais em tiles."
        ),
        lifespan=lifespan,
    )
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )
    app.include_router(router)
    app.include_router(biodiversity_router)
    app.include_router(deter_router)
    return app


app = create_app()
