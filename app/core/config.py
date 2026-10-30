from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "On the Road Bulgaria"
    app_env: str = "development"
    database_url: str = "sqlite:///./on_the_road_bulgaria.db"
    jwt_secret_key: str = "replace-this-with-a-long-random-secret-before-deployment"
    access_token_minutes: int = 60
    upload_dir: Path = Path("./uploads")
    archive_dir: Path = Path("./app/data/archive")
    max_upload_mb: int = 20
    max_pdf_pages: int = 200
    cors_origins: str = "http://127.0.0.1:8000,http://localhost:8000"
    google_routes_api_key: str | None = None  # Server-only key; never return this from an API endpoint.
    google_maps_js_api_key: str | None = None  # Browser key; restrict by HTTP referrer and API.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
