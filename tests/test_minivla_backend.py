import math
from typing import Any

import pytest

from muesli_model_service.app import create_app, select_action_chunk_backend
from muesli_model_service.backends.minivla import (
    MiniVLABackend,
    MiniVLACallInput,
    MiniVLADependencyError,
    MiniVLAPrediction,
)
from muesli_model_service.backends.mock import MockBackend
from muesli_model_service.config import Settings
from muesli_model_service.protocol.envelope import Operation, RequestEnvelope
from muesli_model_service.protocol.statuses import ProtocolStatus
from muesli_model_service.runtime.dispatcher import Dispatcher
from muesli_model_service.runtime.registry import CapabilityRegistry
from muesli_model_service.runtime.sessions import SessionManager
from muesli_model_service.store.frames import FrameStore


class FakeMiniVLAAdapter:
    def __init__(self, *, actions: list[list[float]] | None = None) -> None:
        self.calls: list[MiniVLACallInput] = []
        self.actions = actions or [[0.1, 0.2], [0.3, 0.4]]

    @property
    def required_image_names(self) -> tuple[str, ...]:
        return ("camera1", "camera2")

    @property
    def metadata(self) -> dict[str, Any]:
        return {"required_images": list(self.required_image_names)}

    def predict_action_chunk(self, call: MiniVLACallInput) -> MiniVLAPrediction:
        self.calls.append(call)
        return MiniVLAPrediction(
            actions=self.actions,
            action_dim=len(self.actions[0]),
            chunk_length=len(self.actions),
            metadata={"fake": True},
        )


def make_request_input() -> dict[str, Any]:
    return {
        "instruction": "move the arm to the block",
        "observation": {
            "robot_type": "bridge",
            "state": [0.0, 0.1],
            "images": {
                "camera1": {"path": "/tmp/front.jpg"},
                "camera2": {"path": "/tmp/wrist.jpg"},
            },
        },
    }


async def test_minivla_backend_returns_action_chunk_from_fake_adapter() -> None:
    adapter = FakeMiniVLAAdapter()
    backend = MiniVLABackend(
        SessionManager(),
        model_path="/models/minivla",
        device="cpu",
        dtype="float32",
        unnorm_key="bridge_orig",
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
            {"type": "joint_targets", "values": [0.1, 0.2], "dt_ms": 200},
            {"type": "joint_targets", "values": [0.3, 0.4], "dt_ms": 200},
        ]
    }
    assert step.metadata["backend"] == "minivla"
    assert step.metadata["adapter"] == "openvla-mini"
    assert step.metadata["model_path"] == "/models/minivla"
    assert step.metadata["device"] == "cpu"
    assert step.metadata["dtype"] == "float32"
    assert step.metadata["unnorm_key"] == "bridge_orig"
    assert step.metadata["action_dim"] == 2
    assert step.metadata["chunk_length"] == 2
    assert adapter.calls[0].instruction == "move the arm to the block"


async def test_minivla_backend_resolves_frame_refs(tmp_path) -> None:
    frame_store = FrameStore(tmp_path / "frames")
    camera1 = frame_store.put("camera1", b"fake-front", media_type="image/jpeg", timestamp_ns=100)
    camera2 = frame_store.put("camera2", b"fake-wrist", media_type="image/jpeg", timestamp_ns=200)
    adapter = FakeMiniVLAAdapter()
    backend = MiniVLABackend(
        SessionManager(),
        device="cpu",
        dtype="float32",
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


async def test_minivla_backend_rejects_malformed_model_output() -> None:
    backend = MiniVLABackend(
        SessionManager(),
        device="cpu",
        dtype="float32",
        adapter=FakeMiniVLAAdapter(actions=[[math.nan]]),
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
    assert result.error.code == "invalid_minivla_output"


async def test_minivla_cancelled_session_does_not_call_adapter_again() -> None:
    adapter = FakeMiniVLAAdapter()
    backend = MiniVLABackend(SessionManager(), device="cpu", dtype="float32", adapter=adapter)
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


async def test_minivla_session_routes_to_minivla_when_selected() -> None:
    sessions = SessionManager()
    registry = CapabilityRegistry()
    registry.register("mock", MockBackend(sessions))
    registry.register(
        "minivla",
        MiniVLABackend(
            sessions,
            device="cpu",
            dtype="float32",
            adapter=FakeMiniVLAAdapter(actions=[[0.5, 0.6]]),
        ),
        replace=True,
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
    assert step.metadata["backend"] == "minivla"
    assert step.output["actions"][0]["values"] == [0.5, 0.6]


def test_minivla_backend_reports_descriptor_metadata() -> None:
    backend = MiniVLABackend(
        SessionManager(),
        model_path="Stanford-ILIAD/minivla-vq-bridge-prismatic",
        device="cuda",
        adapter=FakeMiniVLAAdapter(),
    )

    descriptor = backend.describe()[0]

    assert descriptor.id == "cap.vla.action_chunk.v1"
    assert descriptor.mode.value == "session"
    assert descriptor.metadata["backend"] == "minivla"
    assert descriptor.metadata["adapter"] == "openvla-mini"
    assert descriptor.metadata["requires_gpu"] is True
    assert descriptor.metadata["base_model"] is True


def test_action_chunk_backend_default_remains_mock() -> None:
    assert select_action_chunk_backend(Settings()) == "mock"


def test_action_chunk_backend_selects_minivla_explicitly() -> None:
    assert select_action_chunk_backend(Settings(action_chunk_backend="minivla")) == "minivla"


def test_minivla_shortcut_selects_minivla() -> None:
    assert select_action_chunk_backend(Settings(enable_minivla_backend=True)) == "minivla"


def test_smolvla_and_minivla_shortcuts_cannot_both_claim_action_chunk() -> None:
    with pytest.raises(ValueError, match="Only one VLA action backend shortcut"):
        select_action_chunk_backend(
            Settings(enable_smolvla_backend=True, enable_minivla_backend=True)
        )


async def test_app_registers_minivla_backend_after_mock(monkeypatch) -> None:
    class FakeRegisteredBackend(MiniVLABackend):
        def __init__(
            self,
            sessions: SessionManager,
            *,
            model_path: str,
            device: str,
            profile_path: str | None,
            action_type: str,
            dt_ms: int,
            unnorm_key: str,
            dtype: str,
            frame_store: FrameStore | None,
        ) -> None:
            super().__init__(
                sessions,
                model_path=model_path,
                device=device,
                profile_path=profile_path,
                action_type=action_type,
                dt_ms=dt_ms,
                unnorm_key=unnorm_key,
                dtype=dtype,
                adapter=FakeMiniVLAAdapter(),
                frame_store=frame_store,
            )

    monkeypatch.setattr("muesli_model_service.app.MiniVLABackend", FakeRegisteredBackend)
    app = create_app(
        Settings(action_chunk_backend="minivla", minivla_device="cpu", minivla_dtype="float32")
    )
    dispatcher: Dispatcher = app.state.dispatcher

    result = await dispatcher.dispatch(RequestEnvelope(id="describe", op=Operation.DESCRIBE))

    capabilities = {item["id"]: item for item in result.output["capabilities"]}
    assert capabilities["cap.vla.action_chunk.v1"]["metadata"]["backend"] == "minivla"
    assert "cap.model.world.rollout.v1" in capabilities


def test_minivla_backend_fails_fast_when_optional_dependencies_are_missing(monkeypatch) -> None:
    def fail_import(name: str) -> Any:
        if name == "torch":
            raise ImportError(name)
        raise AssertionError(name)

    monkeypatch.setattr("muesli_model_service.backends.minivla.import_module", fail_import)

    with pytest.raises(MiniVLADependencyError):
        MiniVLABackend(SessionManager(), device="cpu")
