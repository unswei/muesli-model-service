import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from muesli_model_service.backends.base import CapabilityBackend
from muesli_model_service.protocol.capabilities import (
    CapabilityDescriptor,
    MethodMode,
)
from muesli_model_service.protocol.envelope import RequestEnvelope, ResponseEnvelope, response
from muesli_model_service.protocol.errors import error
from muesli_model_service.protocol.statuses import ProtocolStatus
from muesli_model_service.runtime.sessions import (
    SessionManager,
    SessionState,
    unknown_session_response,
)


class ReplayStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ProtocolStatus
    output: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReplayFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: str
    mode: MethodMode
    kind: str = "action_model"
    description: str = "Replay capability loaded from fixture"
    steps: list[ReplayStep]
    metadata: dict[str, Any] = Field(default_factory=dict)


def load_replay_fixtures(path: str | Path) -> list[ReplayFixture]:
    replay_path = Path(path)
    if replay_path.suffix == ".jsonl":
        return [
            ReplayFixture.model_validate_json(line)
            for line in replay_path.read_text().splitlines()
            if line.strip()
        ]
    data = json.loads(replay_path.read_text())
    if isinstance(data, list):
        return [ReplayFixture.model_validate(item) for item in data]
    return [ReplayFixture.model_validate(data)]


class ReplayBackend(CapabilityBackend):
    def __init__(
        self,
        sessions: SessionManager,
        fixtures: list[ReplayFixture],
        *,
        backend_key: str = "replay",
    ) -> None:
        self.sessions = sessions
        self.fixtures = {fixture.capability: fixture for fixture in fixtures}
        self.backend_key = backend_key

    @classmethod
    def from_path(cls, sessions: SessionManager, path: str | Path) -> "ReplayBackend":
        return cls(sessions, load_replay_fixtures(path))

    def describe(self) -> list[CapabilityDescriptor]:
        descriptors = []
        for fixture in self.fixtures.values():
            descriptors.append(
                CapabilityDescriptor(
                    id=fixture.capability,
                    kind=fixture.kind,
                    description=fixture.description,
                    mode=fixture.mode,
                    input_schema=f"mms://schemas/{fixture.capability}/input",
                    output_schema=f"mms://schemas/{fixture.capability}/output",
                    supports_cancel=fixture.mode == MethodMode.SESSION,
                    replay={"supported": True, "source": "fixture"},
                    metadata={"backend": "replay", **fixture.metadata},
                )
            )
        return descriptors

    async def invoke(self, request: RequestEnvelope) -> ResponseEnvelope:
        fixture = self.fixtures[str(request.capability)]
        if not fixture.steps:
            return self._exhausted(request.id)
        step = fixture.steps[0]
        return response(
            request.id,
            step.status,
            output=step.output,
            metadata={"backend": "replay", **step.metadata},
        )

    async def start(self, request: RequestEnvelope) -> ResponseEnvelope:
        capability = str(request.capability)
        session = self.sessions.create(
            backend_key=self.backend_key,
            capability=capability,
            method="session",
            data={"steps": self.fixtures[capability].steps},
        )
        return response(
            request.id,
            ProtocolStatus.RUNNING,
            session_id=session.id,
            metadata={"capability": capability, "backend": "replay"},
        )

    async def step(self, request: RequestEnvelope) -> ResponseEnvelope:
        session_id = str(request.session_id or "")
        try:
            session = self.sessions.mark_step(session_id)
        except KeyError:
            return unknown_session_response(request.id, session_id)
        steps: list[ReplayStep] = session.data["steps"]
        if session.cursor >= len(steps):
            session.state = SessionState.FAILED
            return self._exhausted(request.id, session.id)
        step = steps[session.cursor]
        session.cursor += 1
        if step.status == ProtocolStatus.SUCCESS:
            session.state = SessionState.COMPLETED
        return response(
            request.id,
            step.status,
            output=step.output,
            session_id=session.id,
            metadata={"backend": "replay", **step.metadata},
        )

    async def cancel(self, request: RequestEnvelope) -> ResponseEnvelope:
        session_id = str(request.session_id or "")
        try:
            session = self.sessions.require(session_id)
        except KeyError:
            return unknown_session_response(request.id, session_id)
        session.state = SessionState.CANCELLED
        return response(request.id, ProtocolStatus.CANCELLED, session_id=session.id)

    async def status(self, request: RequestEnvelope) -> ResponseEnvelope:
        session_id = str(request.session_id or "")
        try:
            session = self.sessions.require(session_id)
        except KeyError:
            return unknown_session_response(request.id, session_id)
        status = ProtocolStatus.RUNNING
        if session.state == SessionState.COMPLETED:
            status = ProtocolStatus.SUCCESS
        if session.state == SessionState.CANCELLED:
            status = ProtocolStatus.CANCELLED
        if session.state == SessionState.FAILED:
            status = ProtocolStatus.FAILURE
        return response(
            request.id, status, output=self.sessions.to_payload(session), session_id=session.id
        )

    async def close(self, request: RequestEnvelope) -> ResponseEnvelope:
        session_id = str(request.session_id or "")
        try:
            session = self.sessions.close(session_id)
        except KeyError:
            return unknown_session_response(request.id, session_id)
        return response(request.id, ProtocolStatus.SUCCESS, session_id=session.id)

    def _exhausted(self, request_id: str, session_id: str | None = None) -> ResponseEnvelope:
        return response(
            request_id,
            ProtocolStatus.FAILURE,
            session_id=session_id,
            error=error("replay_exhausted", "Replay fixture has no further recorded outputs"),
            metadata={"backend": "replay"},
        )
