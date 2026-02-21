from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HealthBud Backend"
    debug: bool = True
    database_url: str = "sqlite:///./healthbud.db"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    enable_web_search: bool = True
    web_search_max_results: int = 8
    trusted_medical_domains: list[str] = Field(default_factory=lambda: [
        "mayoclinic.org",
        "medlineplus.gov",
        "nhs.uk",
        "who.int",
        "cdc.gov",
        "clevelandclinic.org",
        "webmd.com",
    ])

    cors_origins: list[str] = Field(default_factory=lambda: [
        "http://localhost:3000",
        "http://127.0.0.1:5500",
    ])

    model_config = SettingsConfigDict(
        env_file=".env",
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
