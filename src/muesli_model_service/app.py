from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket

from muesli_model_service import __version__
from muesli_model_service.backends.minivla import MiniVLABackend
from muesli_model_service.backends.mock import MockBackend
from muesli_model_service.backends.replay import ReplayBackend
from muesli_model_service.backends.smolvla import SmolVLABackend
from muesli_model_service.config import Settings
from muesli_model_service.logging import configure_logging
from muesli_model_service.runtime.dispatcher import Dispatcher
from muesli_model_service.runtime.registry import CapabilityRegistry
from muesli_model_service.runtime.sessions import SessionManager
from muesli_model_service.store.frames import FrameStore, FrameStoreError
from muesli_model_service.transports.http import describe_http
from muesli_model_service.transports.websocket import websocket_endpoint


def select_action_chunk_backend(settings: Settings) -> str:
    explicit = settings.action_chunk_backend
    shortcuts = [
        name
        for name, enabled in (
            ("smolvla", settings.enable_smolvla_backend),
            ("minivla", settings.enable_minivla_backend),
        )
        if enabled
    ]
    if explicit != "mock":
        return explicit
    if len(shortcuts) > 1:
        raise ValueError(
            "Only one VLA action backend shortcut can be enabled without MMS_ACTION_CHUNK_BACKEND"
        )
    if shortcuts:
        return shortcuts[0]
    return explicit


def build_runtime(settings: Settings, frame_store: FrameStore | None = None) -> Dispatcher:
    sessions = SessionManager(max_sessions=settings.max_sessions)
    registry = CapabilityRegistry()
    action_chunk_backend = select_action_chunk_backend(settings)
    if settings.enable_mock_backend:
        registry.register("mock", MockBackend(sessions))
    if settings.replay_path:
        registry.register(
            "replay",
            ReplayBackend.from_path(sessions, settings.replay_path),
            replace=settings.enable_mock_backend,
        )
    if action_chunk_backend == "smolvla":
        registry.register(
            "smolvla",
            SmolVLABackend(
                sessions,
                model_path=settings.smolvla_model_path,
                device=settings.smolvla_device,
                profile_path=settings.smolvla_profile_path,
                action_type=settings.smolvla_action_type,
                dt_ms=settings.smolvla_dt_ms,
                frame_store=frame_store,
            ),
            replace=settings.enable_mock_backend or bool(settings.replay_path),
        )
    if action_chunk_backend == "minivla":
        registry.register(
            "minivla",
            MiniVLABackend(
                sessions,
                model_path=settings.minivla_model_path,
                device=settings.minivla_device,
                profile_path=settings.minivla_profile_path,
                action_type=settings.minivla_action_type,
                dt_ms=settings.minivla_dt_ms,
                unnorm_key=settings.minivla_unnorm_key,
                dtype=settings.minivla_dtype,
                frame_store=frame_store,
            ),
            replace=settings.enable_mock_backend or bool(settings.replay_path),
        )
    return Dispatcher(registry)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)
    frame_store = FrameStore(Path(settings.frame_store_root))
    dispatcher = build_runtime(settings, frame_store)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield

    app = FastAPI(
        title="Muesli Model Service",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.dispatcher = dispatcher
    app.state.frame_store = frame_store

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "muesli-model-service", "version": __version__}

    @app.get("/v1/describe")
    async def describe() -> dict:
        result = await describe_http(dispatcher)
        return result.model_dump(mode="json")

    @app.put("/v1/frames/{name}")
    async def put_frame(
        name: str,
        request: Request,
        content_type: str | None = Header(default=None, alias="content-type"),
        timestamp_ns: int | None = Header(default=None, alias="x-mms-timestamp-ns"),
        encoding: str | None = Header(default=None, alias="x-mms-encoding"),
    ) -> dict:
        media_type = content_type or "application/octet-stream"
        content = await request.body()
        try:
            record = frame_store.put(
                name,
                content,
                media_type=media_type,
                timestamp_ns=timestamp_ns,
                encoding=encoding,
            )
        except FrameStoreError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return record.to_payload()

    @app.websocket("/v1/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket_endpoint(websocket, dispatcher)

    return app


app = create_app()
