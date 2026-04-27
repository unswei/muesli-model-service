from abc import ABC, abstractmethod

from muesli_model_service.protocol.capabilities import CapabilityDescriptor
from muesli_model_service.protocol.messages import RequestEnvelope, ResponseEnvelope


class CapabilityBackend(ABC):
    @abstractmethod
    def describe(self) -> list[CapabilityDescriptor]:
        """Return capability descriptors exposed by this backend."""

    async def invoke(self, request: RequestEnvelope) -> ResponseEnvelope:
        raise NotImplementedError

    async def start(self, request: RequestEnvelope) -> ResponseEnvelope:
        raise NotImplementedError

    async def step(self, request: RequestEnvelope) -> ResponseEnvelope:
        raise NotImplementedError

    async def cancel(self, request: RequestEnvelope) -> ResponseEnvelope:
        raise NotImplementedError

    async def status(self, request: RequestEnvelope) -> ResponseEnvelope:
        raise NotImplementedError

    async def close(self, request: RequestEnvelope) -> ResponseEnvelope:
        raise NotImplementedError
