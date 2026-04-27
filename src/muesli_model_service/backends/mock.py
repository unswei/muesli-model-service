from typing import Any

from muesli_model_service.backends.base import CapabilityBackend
from muesli_model_service.protocol.capabilities import (
    CapabilityDescriptor,
    CapabilityMethod,
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

DEFAULT_ACTION_SEQUENCE: list[dict[str, Any]] = [
    {
        "actions": [
            {"type": "joint_targets", "values": [0.10, 0.40, -0.20], "dt_ms": 20},
            {"type": "joint_targets", "values": [0.12, 0.42, -0.18], "dt_ms": 20},
        ]
    },
    {"actions": [{"type": "gripper", "values": [1.0], "dt_ms": 20}]},
]


class MockBackend(CapabilityBackend):
    def __init__(
        self,
        sessions: SessionManager,
        *,
        action_sequence: list[dict[str, Any]] | None = None,
        backend_key: str = "mock",
    ) -> None:
        self.sessions = sessions
        self.action_sequence = action_sequence or DEFAULT_ACTION_SEQUENCE
        self.backend_key = backend_key

    def describe(self) -> list[CapabilityDescriptor]:
        return [
            CapabilityDescriptor(
                id="mock-action-chunker",
                kind="action_model",
                description="Mock capability that emits deterministic action chunks",
                methods=[
                    CapabilityMethod(
                        name="act",
                        mode=MethodMode.SESSION,
                        input_schema="mms://schemas/mock_action_input_v1",
                        output_schema="mms://schemas/action_chunk_v1",
                        supports_cancel=True,
                    )
                ],
                metadata={"backend": "mock", "requires_gpu": False, "expected_latency_ms": 1},
            ),
            CapabilityDescriptor(
                id="mock-world-model",
                kind="world_model",
                description=(
                    "Mock capability that scores or rolls out simple state/action sequences"
                ),
                methods=[
                    CapabilityMethod(
                        name="rollout",
                        mode=MethodMode.INVOKE,
                        input_schema="mms://schemas/rollout_input_v1",
                        output_schema="mms://schemas/rollout_output_v1",
                    ),
                    CapabilityMethod(
                        name="score_trajectory",
                        mode=MethodMode.INVOKE,
                        input_schema="mms://schemas/trajectory_score_input_v1",
                        output_schema="mms://schemas/trajectory_score_output_v1",
                    ),
                ],
                metadata={"backend": "mock", "requires_gpu": False, "expected_latency_ms": 1},
            ),
        ]

    async def invoke(self, request: RequestEnvelope) -> ResponseEnvelope:
        method = request.payload.get("method")
        call_input = request.payload.get("input", {})
        if method == "rollout":
            return self._rollout(request, call_input)
        if method == "score_trajectory":
            return self._score_trajectory(request, call_input)
        return response(
            request.id,
            ProtocolStatus.UNAVAILABLE,
            error=error("method_not_found", f"Mock backend does not support method '{method}'"),
        )

    async def start(self, request: RequestEnvelope) -> ResponseEnvelope:
        session = self.sessions.create(
            backend_key=self.backend_key,
            capability=str(request.payload["capability"]),
            method=str(request.payload["method"]),
            data={"sequence": self.action_sequence},
        )
        return response(
            request.id,
            ProtocolStatus.RUNNING,
            payload={"session": session.id},
            metadata={
                "capability": session.capability,
                "method": session.method,
                "backend": "mock",
            },
        )

    async def step(self, request: RequestEnvelope) -> ResponseEnvelope:
        session_id = str(request.payload.get("session", ""))
        try:
            session = self.sessions.mark_step(session_id)
        except KeyError:
            return unknown_session_response(request.id, session_id)
        if session.state == SessionState.CANCELLED:
            return response(request.id, ProtocolStatus.CANCELLED, payload={"session": session.id})
        sequence: list[dict[str, Any]] = session.data["sequence"]
        if session.cursor < len(sequence):
            output = sequence[session.cursor]
            session.cursor += 1
            return response(
                request.id,
                ProtocolStatus.ACTION_CHUNK,
                payload={"session": session.id, "output": output},
                metadata={"confidence": 0.9, "backend": "mock"},
            )
        session.state = SessionState.COMPLETED
        return response(
            request.id,
            ProtocolStatus.SUCCESS,
            payload={"session": session.id, "output": {"message": "mock action session completed"}},
            metadata={"backend": "mock"},
        )

    async def cancel(self, request: RequestEnvelope) -> ResponseEnvelope:
        session_id = str(request.payload.get("session", ""))
        try:
            session = self.sessions.require(session_id)
        except KeyError:
            return unknown_session_response(request.id, session_id)
        session.state = SessionState.CANCELLED
        return response(request.id, ProtocolStatus.CANCELLED, payload={"session": session.id})

    async def status(self, request: RequestEnvelope) -> ResponseEnvelope:
        session_id = str(request.payload.get("session", ""))
        try:
            session = self.sessions.require(session_id)
        except KeyError:
            return unknown_session_response(request.id, session_id)
        status = (
            ProtocolStatus.CANCELLED
            if session.state == SessionState.CANCELLED
            else ProtocolStatus.RUNNING
        )
        if session.state == SessionState.COMPLETED:
            status = ProtocolStatus.SUCCESS
        return response(request.id, status, payload=self.sessions.to_payload(session))

    async def close(self, request: RequestEnvelope) -> ResponseEnvelope:
        session_id = str(request.payload.get("session", ""))
        try:
            session = self.sessions.close(session_id)
        except KeyError:
            return unknown_session_response(request.id, session_id)
        return response(request.id, ProtocolStatus.SUCCESS, payload={"session": session.id})

    def _rollout(self, request: RequestEnvelope, call_input: dict[str, Any]) -> ResponseEnvelope:
        vector = [float(v) for v in call_input.get("state", {}).get("vector", [])]
        if not vector:
            vector = [0.0]
        predicted_states = []
        current = vector
        for action in call_input.get("actions", []):
            values = [float(v) for v in action.get("values", [])]
            delta = sum(values) / max(len(values), 1)
            current = [round(value + delta, 6) for value in current]
            predicted_states.append({"vector": current})
        horizon = int(call_input.get("horizon", len(predicted_states)))
        predicted_states = predicted_states[:horizon]
        score = round(0.5 + 0.1 * len(predicted_states) + 0.01 * sum(current), 6)
        return response(
            request.id,
            ProtocolStatus.SUCCESS,
            payload={"output": {"predicted_states": predicted_states, "score": score}},
            metadata={"capability": "mock-world-model", "method": "rollout", "backend": "mock"},
        )

    def _score_trajectory(
        self, request: RequestEnvelope, call_input: dict[str, Any]
    ) -> ResponseEnvelope:
        trajectory = call_input.get("trajectory", call_input.get("candidate_trajectory", []))
        total = 0.0
        for item in trajectory:
            values = item.get("values", item.get("vector", [])) if isinstance(item, dict) else item
            if isinstance(values, list):
                total += sum(float(value) for value in values)
        score = round(1.0 / (1.0 + abs(total)), 6)
        return response(
            request.id,
            ProtocolStatus.SUCCESS,
            payload={"output": {"score": score}},
            metadata={
                "capability": "mock-world-model",
                "method": "score_trajectory",
                "backend": "mock",
            },
        )
