import pytest

from muesli_model_service.backends.mock import MockBackend
from muesli_model_service.protocol.capabilities import MethodMode
from muesli_model_service.runtime.registry import CapabilityRegistry
from muesli_model_service.runtime.sessions import SessionManager


def test_mock_capabilities_are_listed() -> None:
    registry = CapabilityRegistry()
    registry.register("mock", MockBackend(SessionManager()))

    capability_ids = {item.id for item in registry.describe()}

    assert "cap.vla.action_chunk.v1" in capability_ids
    assert "cap.vla.propose_nav_goal.v1" in capability_ids
    assert "cap.model.world.rollout.v1" in capability_ids
    assert "cap.model.world.score_trajectory.v1" in capability_ids


def test_duplicate_capability_requires_explicit_replace() -> None:
    sessions = SessionManager()
    registry = CapabilityRegistry()
    registry.register("mock-a", MockBackend(sessions))

    with pytest.raises(ValueError, match="already registered"):
        registry.register("mock-b", MockBackend(sessions))

    registry.register("mock-b", MockBackend(sessions), replace=True)

    resolved = registry.resolve("cap.vla.action_chunk.v1")
    assert resolved.backend_key == "mock-b"


def test_unknown_capability_raises_lookup() -> None:
    registry = CapabilityRegistry()

    with pytest.raises(LookupError):
        registry.resolve("missing")


def test_method_mode_mismatch_raises_value_error() -> None:
    registry = CapabilityRegistry()
    registry.register("mock", MockBackend(SessionManager()))

    with pytest.raises(ValueError):
        registry.resolve("cap.model.world.rollout.v1", MethodMode.SESSION)
