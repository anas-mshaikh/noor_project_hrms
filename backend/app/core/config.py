from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Attendance System"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = []

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    sqlalchemy_echo: bool = False
    data_dir: str = "./data"

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
