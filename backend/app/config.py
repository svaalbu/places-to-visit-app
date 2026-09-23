from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    meshy_api_key: str = ""
    meshy_base_url: str = "https://api.meshy.ai"
    meshy_poll_seconds: float = 4.0
    meshy_timeout_seconds: float = 180.0
    job_dir: Path = Path(__file__).resolve().parent.parent / "data" / "jobs"
    default_size_mm: float = 80.0
    min_size_mm: float = 20.0
    max_size_mm: float = 240.0
    thin_feature_mm: float = 1.2
    max_preview_faces: int = 40_000
    max_export_faces: int = 150_000
    max_upload_bytes: int = 20 * 1024 * 1024


settings = Settings()
