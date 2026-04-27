from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActionType(StrEnum):
    JOINT_TARGETS = "joint_targets"
    JOINT_VELOCITIES = "joint_velocities"
    CARTESIAN_POSE = "cartesian_pose"
    BASE_VELOCITY = "base_velocity"
    GRIPPER = "gripper"
    WAIT = "wait"
    CUSTOM = "custom"


class ActionProposal(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    type: ActionType
    values: list[float] | None = None
    value: Any | None = None
    dt_ms: int | None = Field(default=None, ge=0)
    schema_: str | None = Field(default=None, alias="schema")
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_custom_schema(self) -> "ActionProposal":
        if self.type == ActionType.CUSTOM and not self.schema_:
            msg = "custom action proposals require a schema"
            raise ValueError(msg)
        return self


class ActionChunkOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    actions: list[ActionProposal]


class CustomActionProposal(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal[ActionType.CUSTOM]
    schema_: str = Field(alias="schema")
    value: Any
