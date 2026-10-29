from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API
    app_name: str = "VirtualScreener"
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Paths
    base_dir: Path = Path(__file__).resolve().parents[2]
    models_dir: Path = base_dir / "models"
    uploads_dir: Path = base_dir / "uploads"

    # Chemprop model checkpoint (BindingDB-pretrained)
    chemprop_checkpoint: Path = base_dir / "models" / "chemprop_bindingdb.pt"

    # AutoDock Vina
    vina_exhaustiveness: int = 16
    vina_n_poses: int = 5
    vina_top_k: int = 10  # only dock top-K from ML tier

    # Upload limits (bytes)
    max_protein_bytes: int = 25 * 1024 * 1024
    max_library_bytes: int = 50 * 1024 * 1024

    # Pipeline
    max_molecules: int = 5000
    tier3_top_k: int = 10

    # Job persistence / bounds
    db_path: Path = base_dir / "data" / "jobs.db"
    max_jobs: int = 100
    job_ttl_hours: int = 24

    # Per-IP rate limit for compute endpoints (POST /screen, /sample/screen)
    rate_limit_jobs: int = 10
    rate_limit_window_seconds: int = 60
    # Per-IP cap on simultaneously active jobs (queued/running)
    max_concurrent_jobs_per_ip: int = 2

    # DeepChem model dir
    deepchem_model_dir: Path = base_dir / "models" / "attentivefp"


settings = Settings()

# Ensure dirs exist at import time
settings.models_dir.mkdir(parents=True, exist_ok=True)
settings.uploads_dir.mkdir(parents=True, exist_ok=True)
settings.deepchem_model_dir.mkdir(parents=True, exist_ok=True)
