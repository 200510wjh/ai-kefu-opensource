from functools import lru_cache
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Enterprise Material Factory"
    api_prefix: str = "/api/v1"
    environment: str = "local"
    secret_key: str = "dev-secret-change-me"
    database_url: str = "postgresql://factory:factory@postgres:5432/material_factory"
    redis_url: str = "redis://redis:6379/0"
    storage_backend: str = "local"
    storage_dir: Path = Path("data/storage")
    public_base_url: str = "http://localhost:8001"
    minio_endpoint: str = "minio:9000"
    minio_bucket: str = "material-factory"
    minio_access_key: str = "factory"
    minio_secret_key: str = "factory-secret"


@lru_cache
def get_settings() -> Settings:
    return Settings()
