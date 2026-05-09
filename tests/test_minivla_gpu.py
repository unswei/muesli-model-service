import os
from importlib import import_module

import pytest

from muesli_model_service.backends.minivla import MiniVLABackend
from muesli_model_service.protocol.envelope import Operation, RequestEnvelope
from muesli_model_service.protocol.statuses import ProtocolStatus
from muesli_model_service.runtime.sessions import SessionManager
from muesli_model_service.store.frames import FrameStore

pytestmark = pytest.mark.minivla_gpu


async def test_minivla_backend_runs_one_gated_gpu_request(tmp_path) -> None:
    if os.environ.get("MMS_RUN_MINIVLA_GPU_TESTS") != "1":
        pytest.skip("set MMS_RUN_MINIVLA_GPU_TESTS=1 to run MiniVLA GPU validation")

    frame_path = tmp_path / "camera1.jpg"
    image_module = import_module("PIL.Image")
    image_module.new("RGB", (224, 224), color=(32, 64, 96)).save(frame_path, format="JPEG")

    frame_store = FrameStore(tmp_path / "frames")
    frame = frame_store.put(
        "camera1",
        frame_path.read_bytes(),
        media_type="image/jpeg",
        timestamp_ns=100,
    )
    backend = MiniVLABackend(
        SessionManager(),
        model_path=os.environ.get(
            "MMS_MINIVLA_MODEL_PATH", "Stanford-ILIAD/minivla-vq-bridge-prismatic"
        ),
        device=os.environ.get("MMS_MINIVLA_DEVICE", "cuda"),
        dtype=os.environ.get("MMS_MINIVLA_DTYPE", "bfloat16"),
        unnorm_key=os.environ.get("MMS_MINIVLA_UNNORM_KEY", ""),
        profile_path=os.environ.get("MMS_MINIVLA_PROFILE_PATH"),
        frame_store=frame_store,
    )

    start = await backend.start(
        RequestEnvelope(
            id="minivla-start",
            op=Operation.START,
            capability="cap.vla.action_chunk.v1",
            input={
                "instruction": "move to the target",
                "observation": {
                    "state": [0.0, 0.0, 0.0],
                    "images": {"camera1": {"ref": frame.latest_ref}},
                },
            },
        )
    )
    step = await backend.step(
        RequestEnvelope(id="minivla-step", op=Operation.STEP, session_id=start.session_id)
    )

    assert step.status in {ProtocolStatus.ACTION_CHUNK, ProtocolStatus.INVALID_OUTPUT}
    if step.status == ProtocolStatus.INVALID_OUTPUT:
        assert step.error is not None
        assert step.error.code == "invalid_minivla_output"
