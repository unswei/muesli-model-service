from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool
    details: dict[str, Any] | None = None


def error(
    code: str, message: str, *, retryable: bool = False, details: dict[str, Any] | None = None
) -> ErrorObject:
    return ErrorObject(code=code, message=message, retryable=retryable, details=details)
