from dataclasses import dataclass, field
from enum import StrEnum
from time import time_ns
from typing import Any

from muesli_model_service.protocol.errors import error
from muesli_model_service.protocol.statuses import ProtocolStatus


class SessionState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CLOSED = "closed"


@dataclass
class Session:
    id: str
    backend_key: str
    capability: str
    method: str
    state: SessionState = SessionState.CREATED
    created_at_ns: int = field(default_factory=time_ns)
    last_step_at_ns: int | None = None
    cursor: int = 0
    data: dict[str, Any] = field(default_factory=dict)


class SessionManager:
    def __init__(self, *, max_sessions: int = 128) -> None:
        self._max_sessions = max_sessions
        self._counter = 0
        self._sessions: dict[str, Session] = {}

    def create(
        self, *, backend_key: str, capability: str, method: str, data: dict[str, Any] | None = None
    ) -> Session:
        if (
            len([s for s in self._sessions.values() if s.state != SessionState.CLOSED])
            >= self._max_sessions
        ):
            raise RuntimeError("maximum session count reached")
        self._counter += 1
        session_id = f"sess-{self._counter:06d}"
        session = Session(
            id=session_id,
            backend_key=backend_key,
            capability=capability,
            method=method,
            state=SessionState.RUNNING,
            data=data or {},
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def require(self, session_id: str) -> Session:
        session = self.get(session_id)
        if session is None or session.state == SessionState.CLOSED:
            raise KeyError(session_id)
        return session

    def mark_step(self, session_id: str) -> Session:
        session = self.require(session_id)
        session.last_step_at_ns = time_ns()
        return session

    def close(self, session_id: str) -> Session:
        session = self.require(session_id)
        session.state = SessionState.CLOSED
        return session

    def to_payload(self, session: Session) -> dict[str, Any]:
        return {
            "session": session.id,
            "state": session.state.value,
            "created_at_ns": session.created_at_ns,
            "last_step_at_ns": session.last_step_at_ns,
        }


def unknown_session_response(request_id: str, session_id: str):
    from muesli_model_service.protocol.envelope import response

    return response(
        request_id,
        ProtocolStatus.INVALID_REQUEST,
        session_id=session_id or None,
        error=error(
            "session_not_found",
            f"Session '{session_id}' is not active",
            details={"session_id": session_id},
        ),
    )
