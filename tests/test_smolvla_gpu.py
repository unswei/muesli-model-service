import os

import pytest

from muesli_model_service.backends.smolvla import SmolVLABackend
from muesli_model_service.runtime.sessions import SessionManager

pytestmark = pytest.mark.smolvla_gpu


def test_smolvla_backend_loads_on_configured_gpu() -> None:
    if os.environ.get("MMS_RUN_SMOLVLA_GPU_TESTS") != "1":
        pytest.skip("set MMS_RUN_SMOLVLA_GPU_TESTS=1 to run SmolVLA GPU validation")

    backend = SmolVLABackend(
        SessionManager(),
        model_path=os.environ.get("MMS_SMOLVLA_MODEL_PATH", "lerobot/smolvla_base"),
        device=os.environ.get("MMS_SMOLVLA_DEVICE", "cuda"),
        profile_path=os.environ.get("MMS_SMOLVLA_PROFILE_PATH") or None,
    )

    descriptor = backend.describe()[0]

    assert descriptor.id == "cap.vla.action_chunk.v1"
    assert descriptor.metadata["backend"] == "smolvla"
    assert descriptor.metadata["device"] == os.environ.get("MMS_SMOLVLA_DEVICE", "cuda")
