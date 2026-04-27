import pytest

from muesli_model_service.backends.mock import MockBackend
from muesli_model_service.protocol.capabilities import MethodMode
from muesli_model_service.runtime.registry import CapabilityRegistry
from muesli_model_service.runtime.sessions import SessionManager


def test_mock_capabilities_are_listed() -> None:
    registry = CapabilityRegistry()
    registry.register("mock", MockBackend(SessionManager()))

    capability_ids = {item.id for item in registry.describe()}

    assert "mock-action-chunker" in capability_ids
    assert "mock-world-model" in capability_ids


def test_unknown_capability_raises_lookup() -> None:
    registry = CapabilityRegistry()

    with pytest.raises(LookupError):
        registry.resolve("missing", "act")


def test_unknown_method_raises_lookup() -> None:
    registry = CapabilityRegistry()
    registry.register("mock", MockBackend(SessionManager()))

    with pytest.raises(LookupError):
        registry.resolve("mock-world-model", "missing")


def test_method_mode_mismatch_raises_value_error() -> None:
    registry = CapabilityRegistry()
    registry.register("mock", MockBackend(SessionManager()))

    with pytest.raises(ValueError):
        registry.resolve("mock-world-model", "rollout", MethodMode.SESSION)
