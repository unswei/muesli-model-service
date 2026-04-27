from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from muesli_model_service.protocol.errors import ErrorObject
from muesli_model_service.protocol.statuses import ProtocolStatus

PROTOCOL_VERSION = "0.1"


class Operation(StrEnum):
    DESCRIBE = "describe"
    INVOKE = "invoke"
    START = "start"
    STEP = "step"
    CANCEL = "cancel"
    STATUS = "status"
    CLOSE = "close"


class TraceContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    tree_id: str | None = None
    tick_id: int | None = None
    node_id: str | None = None


class RequestEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = PROTOCOL_VERSION
    id: str = Field(min_length=1)
    op: Operation
    deadline_ms: int | None = Field(default=None, ge=0)
    trace: TraceContext | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ResponseEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = PROTOCOL_VERSION
    id: str = Field(min_length=1)
    status: ProtocolStatus
    payload: dict[str, Any] = Field(default_factory=dict)
    error: ErrorObject | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def response(
    request_id: str,
    status: ProtocolStatus,
    *,
    payload: dict[str, Any] | None = None,
    error: ErrorObject | None = None,
    metadata: dict[str, Any] | None = None,
) -> ResponseEnvelope:
    return ResponseEnvelope(
        id=request_id,
        status=status,
        payload=payload or {},
        error=error,
        metadata=metadata or {},
    )
