from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MMS_", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "info"
    enable_mock_backend: bool = True
    replay_path: str | None = None
    session_ttl_seconds: int = 3600
    max_sessions: int = Field(default=128, ge=1)
