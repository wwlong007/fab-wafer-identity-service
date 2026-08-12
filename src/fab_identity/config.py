from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FAB_", env_file=".env", extra="ignore")

    app_name: str = "fab-wafer-identity-service"
    environment: str = "development"
    database_url: str = (
        "postgresql+psycopg://fab_identity:fab_identity@localhost:55432/fab_identity"
    )
    sql_echo: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout_seconds: int = 15
    request_id_header: str = "X-Request-ID"


@lru_cache
def get_settings() -> Settings:
    return Settings()

