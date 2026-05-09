import logging
from time import perf_counter
from typing import Any

from muesli_model_service.protocol.capabilities import MethodMode
from muesli_model_service.protocol.envelope import (
    Operation,
    RequestEnvelope,
    ResponseEnvelope,
    response,
)
from muesli_model_service.protocol.errors import error
from muesli_model_service.protocol.statuses import ProtocolStatus
from muesli_model_service.runtime.deadlines import with_deadline
from muesli_model_service.runtime.registry import CapabilityRegistry, unavailable_response

LOGGER = logging.getLogger(__name__)


class Dispatcher:
    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    async def dispatch(self, request: RequestEnvelope) -> ResponseEnvelope:
        started = perf_counter()
        try:
            result = await self._dispatch(request)
        except UnavailableResponse as exc:
            result = unavailable_response(request.id, exc.original)
        except TimeoutError:
            result = response(
                request.id,
                ProtocolStatus.TIMEOUT,
                error=error("deadline_exceeded", "Operation exceeded deadline", retryable=True),
            )
        except Exception as exc:
            LOGGER.exception("request_failed")
            result = response(
                request.id,
                ProtocolStatus.INTERNAL_ERROR,
                error=error("internal_error", str(exc), retryable=False),
            )
        self._log_request(request, result, (perf_counter() - started) * 1000)
        return result

    async def _dispatch(self, request: RequestEnvelope) -> ResponseEnvelope:
        if request.op == Operation.DESCRIBE:
            return response(
                request.id,
                ProtocolStatus.SUCCESS,
                output={
                    "capabilities": [
                        item.model_dump(mode="json") for item in self.registry.describe()
                    ]
                },
                metadata={"service": "muesli-model-service", "service_version": "0.2.0"},
            )
        if request.op == Operation.INVOKE:
            resolved = self._resolve(request, MethodMode.INVOKE)
            if isinstance(resolved, ResponseEnvelope):
                return resolved
            return await with_deadline(resolved.backend.invoke(request), request.deadline_ms)
        if request.op == Operation.START:
            resolved = self._resolve(request, MethodMode.SESSION)
            if isinstance(resolved, ResponseEnvelope):
                return resolved
            return await with_deadline(resolved.backend.start(request), request.deadline_ms)
        if request.op in {Operation.STEP, Operation.CANCEL, Operation.STATUS, Operation.CLOSE}:
            session_id = request.session_id
            if not isinstance(session_id, str) or not session_id:
                return response(
                    request.id,
                    ProtocolStatus.INVALID_REQUEST,
                    error=error("missing_session", "Session operation requires a session ID"),
                )
            backend = self._backend_for_session(session_id)
            if backend is None:
                return response(
                    request.id,
                    ProtocolStatus.INVALID_REQUEST,
                    error=error(
                        "session_not_found",
                        f"Session '{session_id}' is not active",
                        details={"session": session_id},
                    ),
                )
            call = getattr(backend, request.op.value)
            return await with_deadline(call(request), request.deadline_ms)
        return response(
            request.id,
            ProtocolStatus.INVALID_REQUEST,
            error=error("unsupported_operation", f"Unsupported operation '{request.op}'"),
        )

    def _resolve(self, request: RequestEnvelope, mode: MethodMode):
        capability = request.capability
        if not isinstance(capability, str):
            return response(
                request.id,
                ProtocolStatus.INVALID_REQUEST,
                error=error(
                    "missing_capability",
                    "Operation requires capability",
                ),
            )
        resolved = self._resolve_capability(capability, mode)
        if isinstance(resolved, ResponseEnvelope):
            return resolved
        return resolved

    def _resolve_capability(self, capability: str, mode: MethodMode):
        try:
            return self.registry.resolve(capability, mode)
        except (LookupError, ValueError) as exc:
            raise UnavailableResponse(exc) from exc

    def _backend_for_session(self, session_id: str):
        for backend_key, backend in self.registry._backends.items():
            sessions = getattr(backend, "sessions", None)
            session = sessions.get(session_id) if sessions is not None else None
            if session is not None and session.backend_key == backend_key:
                return backend
        return None

    def _log_request(
        self, request: RequestEnvelope, result: ResponseEnvelope, duration_ms: float
    ) -> None:
        structured: dict[str, Any] = {
            "request_id": request.id,
            "op": request.op.value,
            "capability": request.capability,
            "session_id": request.session_id or result.session_id,
            "status": result.status.value,
            "duration_ms": round(duration_ms, 3),
        }
        if result.error is not None:
            structured["error_code"] = result.error.code
        LOGGER.info("request_completed", extra={"structured": structured})


class UnavailableResponse(Exception):
    def __init__(self, original: LookupError | ValueError) -> None:
        self.original = original
        super().__init__(str(original))


async def dispatch_or_unavailable(
    dispatcher: Dispatcher, request: RequestEnvelope
) -> ResponseEnvelope:
    try:
        return await dispatcher.dispatch(request)
    except UnavailableResponse as exc:
        return unavailable_response(request.id, exc.original)
