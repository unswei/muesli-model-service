from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MethodMode(StrEnum):
    INVOKE = "invoke"
    SESSION = "session"


class CapabilityDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    description: str
    mode: MethodMode
    input_schema: str
    output_schema: str
    supports_cancel: bool = False
    supports_deadline: bool = True
    freshness: dict[str, Any] = Field(default_factory=dict)
    replay: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
