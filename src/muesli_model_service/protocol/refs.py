from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DataReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str = Field(min_length=1)
    media_type: str | None = None
    shape: list[int] | None = None
    encoding: str | None = None
    timestamp_ns: int | None = None
    metadata: dict[str, Any] | None = None


class Observation(BaseModel):
    model_config = ConfigDict(extra="allow")
