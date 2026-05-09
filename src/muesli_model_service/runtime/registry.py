from dataclasses import dataclass

from muesli_model_service.backends.base import CapabilityBackend
from muesli_model_service.protocol.capabilities import CapabilityDescriptor, MethodMode
from muesli_model_service.protocol.errors import error
from muesli_model_service.protocol.statuses import ProtocolStatus


@dataclass(frozen=True)
class ResolvedCapability:
    backend_key: str
    backend: CapabilityBackend
    descriptor: CapabilityDescriptor
    method_mode: MethodMode


class CapabilityRegistry:
    def __init__(self) -> None:
        self._backends: dict[str, CapabilityBackend] = {}
        self._capability_index: dict[str, tuple[str, CapabilityDescriptor]] = {}

    def register(self, key: str, backend: CapabilityBackend, *, replace: bool = False) -> None:
        self._backends[key] = backend
        for descriptor in backend.describe():
            if descriptor.id in self._capability_index and not replace:
                existing_key, _ = self._capability_index[descriptor.id]
                raise ValueError(
                    f"Capability '{descriptor.id}' is already registered by '{existing_key}'"
                )
            self._capability_index[descriptor.id] = (key, descriptor)

    def describe(self) -> list[CapabilityDescriptor]:
        return [descriptor for _, descriptor in self._capability_index.values()]

    def resolve(self, capability: str, mode: MethodMode | None = None) -> ResolvedCapability:
        if capability not in self._capability_index:
            raise LookupError(
                error(
                    "capability_not_found",
                    f"Capability '{capability}' is not registered",
                    details={"capability": capability},
                ).model_dump()
            )
        backend_key, descriptor = self._capability_index[capability]
        if mode is not None and descriptor.mode != mode:
            raise ValueError(
                error(
                    "method_mode_mismatch",
                    f"Capability '{capability}' does not support {mode.value} mode",
                    details={
                        "capability": capability,
                        "expected_mode": mode.value,
                        "actual_mode": descriptor.mode.value,
                    },
                ).model_dump()
            )
        return ResolvedCapability(
            backend_key=backend_key,
            backend=self._backends[backend_key],
            descriptor=descriptor,
            method_mode=descriptor.mode,
        )


def unavailable_response(request_id: str, exc: LookupError | ValueError):
    from ast import literal_eval

    from muesli_model_service.protocol.envelope import response
    from muesli_model_service.protocol.errors import ErrorObject

    raw = exc.args[0]
    details = literal_eval(raw) if isinstance(raw, str) else raw
    return response(
        request_id,
        ProtocolStatus.UNAVAILABLE,
        error=ErrorObject.model_validate(details),
    )
