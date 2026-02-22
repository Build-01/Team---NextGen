from functools import lru_cache
import os
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "HealthBud Backend"
    debug: bool = True
    database_url: str = Field(
        default_factory=lambda: "sqlite:////tmp/healthbud.db"
        if os.getenv("VERCEL") == "1"
        else "sqlite:///./healthbud.db"
    )

    llm_provider: str = "openrouter"
    openrouter_api_key: str | None = None
    openrouter_model: str = "openrouter/auto"
    openrouter_site_url: str = "http://localhost:5500"
    openrouter_app_name: str = "HealthBud"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    memory_turn_window: int = 8
    enable_web_search: bool = True
    web_search_max_results: int = 8
    trusted_medical_domains: Annotated[list[str], NoDecode] = Field(default_factory=lambda: [
        "mayoclinic.org",
        "medlineplus.gov",
        "nhs.uk",
        "who.int",
        "cdc.gov",
        "clevelandclinic.org",
        "webmd.com",
    ])

    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: [
        "http://localhost:3000",
        "http://127.0.0.1:5500",
    ])
    trusted_hosts: Annotated[list[str], NoDecode] = Field(default_factory=lambda: [
        "localhost",
        "127.0.0.1",
        "*.vercel.app",
    ])
    chat_assess_rate_limit_per_min: int = 40
    chat_analyze_rate_limit_per_min: int = 20

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("trusted_medical_domains", mode="before")
    @classmethod
    def parse_trusted_domains(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def parse_trusted_hosts(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
