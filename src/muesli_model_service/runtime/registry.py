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
    method_name: str
    method_mode: MethodMode


class CapabilityRegistry:
    def __init__(self) -> None:
        self._backends: dict[str, CapabilityBackend] = {}
        self._capability_index: dict[str, tuple[str, CapabilityDescriptor]] = {}

    def register(self, key: str, backend: CapabilityBackend) -> None:
        self._backends[key] = backend
        for descriptor in backend.describe():
            self._capability_index[descriptor.id] = (key, descriptor)

    def describe(self) -> list[CapabilityDescriptor]:
        return [descriptor for _, descriptor in self._capability_index.values()]

    def resolve(
        self, capability: str, method: str, mode: MethodMode | None = None
    ) -> ResolvedCapability:
        if capability not in self._capability_index:
            raise LookupError(
                error(
                    "capability_not_found",
                    f"Capability '{capability}' is not registered",
                    details={"capability": capability},
                ).model_dump()
            )
        backend_key, descriptor = self._capability_index[capability]
        method_descriptor = next((item for item in descriptor.methods if item.name == method), None)
        if method_descriptor is None:
            raise LookupError(
                error(
                    "method_not_found",
                    f"Method '{method}' is not registered for capability '{capability}'",
                    details={"capability": capability, "method": method},
                ).model_dump()
            )
        if mode is not None and method_descriptor.mode != mode:
            raise ValueError(
                error(
                    "method_mode_mismatch",
                    f"Method '{method}' does not support {mode.value} mode",
                    details={
                        "capability": capability,
                        "method": method,
                        "expected_mode": mode.value,
                        "actual_mode": method_descriptor.mode.value,
                    },
                ).model_dump()
            )
        return ResolvedCapability(
            backend_key=backend_key,
            backend=self._backends[backend_key],
            descriptor=descriptor,
            method_name=method_descriptor.name,
            method_mode=method_descriptor.mode,
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
