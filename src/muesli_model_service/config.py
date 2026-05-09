from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MMS_", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "info"
    enable_mock_backend: bool = True
    action_chunk_backend: Literal["mock", "smolvla", "minivla"] = "mock"
    enable_smolvla_backend: bool = False
    enable_minivla_backend: bool = False
    replay_path: str | None = None
    session_ttl_seconds: int = 3600
    max_sessions: int = Field(default=128, ge=1)
    frame_store_root: str = "/tmp/muesli-model-service/frames"
    smolvla_model_path: str = "lerobot/smolvla_base"
    smolvla_device: str = "cuda"
    smolvla_profile_path: str | None = None
    smolvla_action_type: str = "joint_targets"
    smolvla_dt_ms: int = Field(default=33, ge=0)
    minivla_model_path: str = "Stanford-ILIAD/minivla-vq-bridge-prismatic"
    minivla_device: str = "cuda"
    minivla_profile_path: str | None = None
    minivla_action_type: str = "joint_targets"
    minivla_dt_ms: int = Field(default=200, ge=0)
    minivla_unnorm_key: str = ""
    minivla_dtype: str = "bfloat16"
    minivla_worker_url: str | None = None
