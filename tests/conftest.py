from collections.abc import Iterator

import pytest

from muesli_model_service.backends.mock import MockBackend
from muesli_model_service.runtime.dispatcher import Dispatcher
from muesli_model_service.runtime.registry import CapabilityRegistry
from muesli_model_service.runtime.sessions import SessionManager


@pytest.fixture
def sessions() -> SessionManager:
    return SessionManager()


@pytest.fixture
def dispatcher(sessions: SessionManager) -> Iterator[Dispatcher]:
    registry = CapabilityRegistry()
    registry.register("mock", MockBackend(sessions))
    yield Dispatcher(registry)
