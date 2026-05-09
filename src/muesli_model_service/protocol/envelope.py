from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from muesli_model_service.protocol.errors import ErrorObject
from muesli_model_service.protocol.statuses import ProtocolStatus

PROTOCOL_VERSION = "0.2"


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

    run_id: str | None = None
    tree_id: str | None = None
    tick_id: int | None = None
    node_id: str | None = None


class ReplayDirective(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "live"
    key: str | None = None


class RequestEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["0.2"] = PROTOCOL_VERSION
    id: str = Field(min_length=1)
    op: Operation
    capability: str | None = Field(default=None, min_length=1)
    deadline_ms: int | None = Field(default=None, ge=0)
    trace: TraceContext | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    refs: list[dict[str, Any]] = Field(default_factory=list)
    replay: ReplayDirective = Field(default_factory=ReplayDirective)
    session_id: str | None = Field(default=None, min_length=1)


class ResponseEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["0.2"] = PROTOCOL_VERSION
    id: str = Field(min_length=1)
    status: ProtocolStatus
    output: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None
    error: ErrorObject | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def response(
    request_id: str,
    status: ProtocolStatus,
    *,
    output: dict[str, Any] | None = None,
    session_id: str | None = None,
    error: ErrorObject | None = None,
    metadata: dict[str, Any] | None = None,
) -> ResponseEnvelope:
    return ResponseEnvelope(
        id=request_id,
        status=status,
        output=output or {},
        session_id=session_id,
        error=error,
        metadata=metadata or {},
    )
