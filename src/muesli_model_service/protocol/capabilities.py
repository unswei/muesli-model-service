from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MethodMode(StrEnum):
    INVOKE = "invoke"
    SESSION = "session"


class CapabilityMethod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    mode: MethodMode
    input_schema: str
    output_schema: str
    supports_cancel: bool = False
    supports_deadline: bool = True


class CapabilityDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    description: str
    methods: list[CapabilityMethod]
    metadata: dict[str, Any] = Field(default_factory=dict)
