from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket

from muesli_model_service import __version__
from muesli_model_service.backends.mock import MockBackend
from muesli_model_service.backends.replay import ReplayBackend
from muesli_model_service.backends.smolvla import SmolVLABackend
from muesli_model_service.config import Settings
from muesli_model_service.logging import configure_logging
from muesli_model_service.runtime.dispatcher import Dispatcher
from muesli_model_service.runtime.registry import CapabilityRegistry
from muesli_model_service.runtime.sessions import SessionManager
from muesli_model_service.transports.http import describe_http
from muesli_model_service.transports.websocket import websocket_endpoint


def build_runtime(settings: Settings) -> Dispatcher:
    sessions = SessionManager(max_sessions=settings.max_sessions)
    registry = CapabilityRegistry()
    if settings.enable_mock_backend:
        registry.register("mock", MockBackend(sessions))
    if settings.replay_path:
        registry.register("replay", ReplayBackend.from_path(sessions, settings.replay_path))
    if settings.enable_smolvla_backend:
        registry.register(
            "smolvla",
            SmolVLABackend(
                sessions,
                model_path=settings.smolvla_model_path,
                device=settings.smolvla_device,
                profile_path=settings.smolvla_profile_path,
                action_type=settings.smolvla_action_type,
                dt_ms=settings.smolvla_dt_ms,
            ),
        )
    return Dispatcher(registry)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)
    dispatcher = build_runtime(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield

    app = FastAPI(
        title="Muesli Model Service",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.dispatcher = dispatcher

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "muesli-model-service", "version": __version__}

    @app.get("/v1/describe")
    async def describe() -> dict:
        result = await describe_http(dispatcher)
        return result.model_dump(mode="json")

    @app.websocket("/v1/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket_endpoint(websocket, dispatcher)

    return app


app = create_app()
