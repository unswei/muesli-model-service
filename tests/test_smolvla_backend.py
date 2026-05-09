import math
from typing import Any

import pytest

from muesli_model_service.app import create_app
from muesli_model_service.backends.mock import MockBackend
from muesli_model_service.backends.smolvla import (
    SmolVLABackend,
    SmolVLACallInput,
    SmolVLADependencyError,
    SmolVLAPrediction,
)
from muesli_model_service.config import Settings
from muesli_model_service.protocol.envelope import Operation, RequestEnvelope
from muesli_model_service.protocol.statuses import ProtocolStatus
from muesli_model_service.runtime.dispatcher import Dispatcher
from muesli_model_service.runtime.registry import CapabilityRegistry
from muesli_model_service.runtime.sessions import SessionManager
from muesli_model_service.store.frames import FrameStore


class FakeSmolVLAAdapter:
    def __init__(self, *, actions: list[list[float]] | None = None) -> None:
        self.calls: list[SmolVLACallInput] = []
        self.actions = actions or [[0.1, 0.2], [0.3, 0.4]]

    @property
    def required_image_names(self) -> tuple[str, ...]:
        return ("camera1", "camera2")

    @property
    def metadata(self) -> dict[str, Any]:
        return {"required_images": list(self.required_image_names)}

    def predict_action_chunk(self, call: SmolVLACallInput) -> SmolVLAPrediction:
        self.calls.append(call)
        return SmolVLAPrediction(
            actions=self.actions,
            action_dim=len(self.actions[0]),
            chunk_length=len(self.actions),
            metadata={"fake": True},
        )


def make_request_input() -> dict[str, Any]:
    return {
        "instruction": "pick up the block",
        "observation": {
            "robot_type": "so100_follower",
            "state": [0.0, 0.1],
            "images": {
                "camera1": {"path": "/tmp/front.png"},
                "camera2": {"path": "/tmp/wrist.png"},
            },
        },
    }


async def test_smolvla_backend_returns_action_chunk_from_fake_adapter() -> None:
    adapter = FakeSmolVLAAdapter()
    backend = SmolVLABackend(
        SessionManager(),
        model_path="/models/task-smolvla",
        device="cpu",
        adapter=adapter,
    )

    start = await backend.start(
        RequestEnvelope(
            id="start",
            op=Operation.START,
            capability="cap.vla.action_chunk.v1",
            input=make_request_input(),
        )
    )
    step = await backend.step(
        RequestEnvelope(id="step", op=Operation.STEP, session_id=start.session_id)
    )

    assert step.status == ProtocolStatus.ACTION_CHUNK
    assert step.output == {
        "actions": [
            {"type": "joint_targets", "values": [0.1, 0.2], "dt_ms": 33},
            {"type": "joint_targets", "values": [0.3, 0.4], "dt_ms": 33},
        ]
    }
    assert step.metadata["backend"] == "smolvla"
    assert step.metadata["adapter"] == "lerobot"
    assert step.metadata["model_path"] == "/models/task-smolvla"
    assert step.metadata["device"] == "cpu"
    assert step.metadata["action_dim"] == 2
    assert step.metadata["chunk_length"] == 2
    assert step.metadata["base_model"] is False
    assert adapter.calls[0].instruction == "pick up the block"


async def test_smolvla_backend_rejects_missing_required_image() -> None:
    payload = make_request_input()
    del payload["observation"]["images"]["camera2"]
    backend = SmolVLABackend(SessionManager(), device="cpu", adapter=FakeSmolVLAAdapter())

    result = await backend.start(
        RequestEnvelope(
            id="start",
            op=Operation.START,
            capability="cap.vla.action_chunk.v1",
            input=payload,
        )
    )

    assert result.id == "start"
    assert result.status == ProtocolStatus.INVALID_REQUEST
    assert result.error is not None
    assert result.error.code == "missing_image"


async def test_smolvla_backend_resolves_frame_refs(tmp_path) -> None:
    frame_store = FrameStore(tmp_path / "frames")
    camera1 = frame_store.put("camera1", b"fake-front", media_type="image/jpeg", timestamp_ns=100)
    camera2 = frame_store.put("camera2", b"fake-wrist", media_type="image/jpeg", timestamp_ns=200)
    adapter = FakeSmolVLAAdapter()
    backend = SmolVLABackend(
        SessionManager(),
        device="cpu",
        adapter=adapter,
        frame_store=frame_store,
    )
    payload = make_request_input()
    payload["observation"]["images"] = {
        "camera1": {"ref": "frame://camera1/latest"},
        "camera2": {"ref": "frame://camera2/latest"},
    }

    start = await backend.start(
        RequestEnvelope(
            id="start",
            op=Operation.START,
            capability="cap.vla.action_chunk.v1",
            input=payload,
        )
    )
    step = await backend.step(
        RequestEnvelope(id="step", op=Operation.STEP, session_id=start.session_id)
    )

    assert step.status == ProtocolStatus.ACTION_CHUNK
    images = adapter.calls[0].observation["images"]
    assert images["camera1"]["path"] == str(camera1.path)
    assert images["camera1"]["resolved_ref"] == "frame://camera1/100"
    assert images["camera2"]["path"] == str(camera2.path)
    assert images["camera2"]["resolved_ref"] == "frame://camera2/200"


async def test_smolvla_backend_rejects_malformed_model_output() -> None:
    backend = SmolVLABackend(
        SessionManager(),
        device="cpu",
        adapter=FakeSmolVLAAdapter(actions=[[math.nan]]),
    )
    start = await backend.start(
        RequestEnvelope(
            id="start",
            op=Operation.START,
            capability="cap.vla.action_chunk.v1",
            input=make_request_input(),
        )
    )

    result = await backend.step(
        RequestEnvelope(id="step", op=Operation.STEP, session_id=start.session_id)
    )

    assert result.status == ProtocolStatus.INVALID_OUTPUT
    assert result.error is not None
    assert result.error.code == "invalid_smolvla_output"


async def test_smolvla_session_routes_to_smolvla_when_mock_is_also_registered() -> None:
    sessions = SessionManager()
    registry = CapabilityRegistry()
    registry.register("mock", MockBackend(sessions))
    registry.register(
        "smolvla", SmolVLABackend(sessions, device="cpu", adapter=FakeSmolVLAAdapter())
    )
    dispatcher = Dispatcher(registry)

    start = await dispatcher.dispatch(
        RequestEnvelope(
            id="start",
            op=Operation.START,
            capability="cap.vla.action_chunk.v1",
            input=make_request_input(),
        )
    )
    step = await dispatcher.dispatch(
        RequestEnvelope(id="step", op=Operation.STEP, session_id=start.session_id)
    )

    assert step.status == ProtocolStatus.ACTION_CHUNK
    assert step.metadata["backend"] == "smolvla"
    assert step.output["actions"][0]["values"] == [0.1, 0.2]


async def test_smolvla_cancelled_session_does_not_call_adapter_again() -> None:
    adapter = FakeSmolVLAAdapter()
    backend = SmolVLABackend(SessionManager(), device="cpu", adapter=adapter)
    start = await backend.start(
        RequestEnvelope(
            id="start",
            op=Operation.START,
            capability="cap.vla.action_chunk.v1",
            input=make_request_input(),
        )
    )

    cancel = await backend.cancel(
        RequestEnvelope(id="cancel", op=Operation.CANCEL, session_id=start.session_id)
    )
    step = await backend.step(
        RequestEnvelope(id="step", op=Operation.STEP, session_id=start.session_id)
    )

    assert cancel.status == ProtocolStatus.CANCELLED
    assert step.status == ProtocolStatus.CANCELLED
    assert adapter.calls == []


def test_smolvla_backend_reports_descriptor_metadata() -> None:
    backend = SmolVLABackend(
        SessionManager(),
        model_path="lerobot/smolvla_base",
        device="cuda",
        adapter=FakeSmolVLAAdapter(),
    )

    descriptor = backend.describe()[0]

    assert descriptor.id == "cap.vla.action_chunk.v1"
    assert descriptor.mode.value == "session"
    assert descriptor.metadata["backend"] == "smolvla"
    assert descriptor.metadata["adapter"] == "lerobot"
    assert descriptor.metadata["model_path"] == "lerobot/smolvla_base"
    assert descriptor.metadata["requires_gpu"] is True
    assert descriptor.metadata["base_model"] is True


async def test_app_registers_smolvla_backend_after_mock(monkeypatch) -> None:
    class FakeRegisteredBackend(SmolVLABackend):
        def __init__(
            self,
            sessions: SessionManager,
            *,
            model_path: str,
            device: str,
            profile_path: str | None,
            action_type: str,
            dt_ms: int,
            frame_store: FrameStore | None,
        ) -> None:
            super().__init__(
                sessions,
                model_path=model_path,
                device=device,
                profile_path=profile_path,
                action_type=action_type,
                dt_ms=dt_ms,
                adapter=FakeSmolVLAAdapter(),
                frame_store=frame_store,
            )

    monkeypatch.setattr("muesli_model_service.app.SmolVLABackend", FakeRegisteredBackend)
    app = create_app(Settings(enable_smolvla_backend=True, smolvla_device="cpu"))
    dispatcher: Dispatcher = app.state.dispatcher

    result = await dispatcher.dispatch(RequestEnvelope(id="describe", op=Operation.DESCRIBE))

    capabilities = {item["id"]: item for item in result.output["capabilities"]}
    assert capabilities["cap.vla.action_chunk.v1"]["metadata"]["backend"] == "smolvla"
    assert "cap.model.world.rollout.v1" in capabilities


def test_smolvla_backend_fails_fast_when_optional_dependencies_are_missing(monkeypatch) -> None:
    def fail_import(name: str) -> Any:
        if name == "torch":
            raise ImportError(name)
        raise AssertionError(name)

    monkeypatch.setattr("muesli_model_service.backends.smolvla.import_module", fail_import)

    with pytest.raises(SmolVLADependencyError):
        SmolVLABackend(SessionManager(), device="cpu")
