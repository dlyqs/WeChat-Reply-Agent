"""Backend-only configuration. No model key is needed for the Phase 1 probes."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    wechat_adapter: Literal["replica", "mac_ax", "fake"] = "replica"
    wechat_profile: Path = Path(".local/wechat-profile.json")
    wechat_account_ref: str = "local-account"
    wechat_allowlist: list[str] = Field(default_factory=list)
    wechat_db_root: Path | None = None
    wechat_ocr_enabled: bool = True
    wechat_uia_gate_enabled: bool = True
    send_mode: Literal["dry-run", "live"] = "dry-run"
    data_dir: Path = Path(".local")
    poll_interval_seconds: float = Field(default=15, ge=0.1, le=60)

    @field_validator("wechat_account_ref")
    @classmethod
    def valid_account(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("account reference must be nonempty")
        return value

    @field_validator("wechat_allowlist")
    @classmethod
    def unique_aliases(cls, value: list[str]) -> list[str]:
        if any(not alias.strip() or alias != alias.strip() for alias in value):
            raise ValueError("aliases must be nonempty and have no surrounding whitespace")
        if len(set(value)) != len(value):
            raise ValueError("aliases must be unique")
        return value
