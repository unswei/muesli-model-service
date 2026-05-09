from typing import Any

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
                id="cap.vla.action_chunk.v1",
                kind="action_model",
                description="Deterministic mock VLA action chunk proposal capability",
                mode=MethodMode.SESSION,
                input_schema="mms://schemas/cap.vla.action_chunk.request.v1",
                output_schema="mms://schemas/cap.vla.action_chunk.result.v1",
                supports_cancel=True,
                freshness={"expects_fresh_observation": True},
                replay={"supported": True},
                metadata={
                    "backend": "mock-action-chunker",
                    "adapter": "mock",
                    "requires_gpu": False,
                    "expected_latency_ms": 1,
                },
            ),
            CapabilityDescriptor(
                id="cap.vla.propose_nav_goal.v1",
                kind="navigation_goal_model",
                description="Deterministic mock VLA navigation goal proposal capability",
                mode=MethodMode.INVOKE,
                input_schema="mms://schemas/cap.vla.propose_nav_goal.request.v1",
                output_schema="mms://schemas/cap.vla.propose_nav_goal.result.v1",
                replay={"supported": True},
                metadata={
                    "backend": "mock-nav-goal",
                    "adapter": "mock",
                    "requires_gpu": False,
                    "expected_latency_ms": 1,
                },
            ),
            CapabilityDescriptor(
                id="cap.model.world.rollout.v1",
                kind="world_model",
                description="Deterministic mock world-model rollout capability",
                mode=MethodMode.INVOKE,
                input_schema="mms://schemas/cap.model.world.rollout.request.v1",
                output_schema="mms://schemas/cap.model.world.rollout.result.v1",
                replay={"supported": True},
                metadata={
                    "backend": "mock-world-model",
                    "adapter": "mock",
                    "requires_gpu": False,
                    "expected_latency_ms": 1,
                },
            ),
            CapabilityDescriptor(
                id="cap.model.world.score_trajectory.v1",
                kind="world_model",
                description="Deterministic mock world-model trajectory scoring capability",
                mode=MethodMode.INVOKE,
                input_schema="mms://schemas/cap.model.world.score_trajectory.request.v1",
                output_schema="mms://schemas/cap.model.world.score_trajectory.result.v1",
                replay={"supported": True},
                metadata={
                    "backend": "mock-world-model",
                    "adapter": "mock",
                    "requires_gpu": False,
                    "expected_latency_ms": 1,
                },
            ),
        ]

    async def invoke(self, request: RequestEnvelope) -> ResponseEnvelope:
        call_input = request.input
        if request.capability == "cap.model.world.rollout.v1":
            return self._rollout(request, call_input)
        if request.capability == "cap.model.world.score_trajectory.v1":
            return self._score_trajectory(request, call_input)
        if request.capability == "cap.vla.propose_nav_goal.v1":
            return self._propose_nav_goal(request, call_input)
        return response(
            request.id,
            ProtocolStatus.UNAVAILABLE,
            error=error(
                "capability_not_found",
                f"Mock backend does not support capability '{request.capability}'",
            ),
        )

    async def start(self, request: RequestEnvelope) -> ResponseEnvelope:
        session = self.sessions.create(
            backend_key=self.backend_key,
            capability=str(request.capability),
            method="session",
            data={"sequence": self.action_sequence},
        )
        return response(
            request.id,
            ProtocolStatus.RUNNING,
            session_id=session.id,
            metadata={
                "capability": session.capability,
                "backend": "mock-action-chunker",
                "adapter": "mock",
            },
        )

    async def step(self, request: RequestEnvelope) -> ResponseEnvelope:
        session_id = str(request.session_id or "")
        try:
            session = self.sessions.mark_step(session_id)
        except KeyError:
            return unknown_session_response(request.id, session_id)
        if session.state == SessionState.CANCELLED:
            return response(request.id, ProtocolStatus.CANCELLED, session_id=session.id)
        sequence: list[dict[str, Any]] = session.data["sequence"]
        if session.cursor < len(sequence):
            output = sequence[session.cursor]
            session.cursor += 1
            return response(
                request.id,
                ProtocolStatus.ACTION_CHUNK,
                output=output,
                session_id=session.id,
                metadata={"confidence": 0.9, "backend": "mock-action-chunker", "adapter": "mock"},
            )
        session.state = SessionState.COMPLETED
        return response(
            request.id,
            ProtocolStatus.SUCCESS,
            output={"message": "mock action session completed"},
            session_id=session.id,
            metadata={"backend": "mock-action-chunker", "adapter": "mock"},
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
        status = (
            ProtocolStatus.CANCELLED
            if session.state == SessionState.CANCELLED
            else ProtocolStatus.RUNNING
        )
        if session.state == SessionState.COMPLETED:
            status = ProtocolStatus.SUCCESS
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
            output={"predicted_states": predicted_states, "score": score},
            metadata={
                "capability": "cap.model.world.rollout.v1",
                "backend": "mock-world-model",
                "adapter": "mock",
            },
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
            output={"score": score},
            metadata={
                "capability": "cap.model.world.score_trajectory.v1",
                "backend": "mock-world-model",
                "adapter": "mock",
            },
        )

    def _propose_nav_goal(
        self, request: RequestEnvelope, call_input: dict[str, Any]
    ) -> ResponseEnvelope:
        goal = call_input.get("goal_hint", {"x": 1.0, "y": 0.0, "theta": 0.0})
        if not isinstance(goal, dict):
            goal = {"x": 1.0, "y": 0.0, "theta": 0.0}
        return response(
            request.id,
            ProtocolStatus.SUCCESS,
            output={
                "goal": {
                    "x": float(goal.get("x", 1.0)),
                    "y": float(goal.get("y", 0.0)),
                    "theta": float(goal.get("theta", 0.0)),
                    "frame": str(goal.get("frame", "map")),
                },
                "confidence": 0.75,
            },
            metadata={
                "capability": "cap.vla.propose_nav_goal.v1",
                "backend": "mock-nav-goal",
                "adapter": "mock",
            },
        )
