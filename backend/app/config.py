from functools import lru_cache
import os
from pathlib import Path

from pydantic import BaseModel, Field


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    app_name: str = "Bioinformatics Agent"
    app_version: str = "0.1.0"
    environment: str = "local"
    project_root: Path = Field(default_factory=_project_root)
    storage_dir: Path = Field(default_factory=lambda: _project_root() / ".storage")
    database_url: str = "sqlite:///./bioinformatics_agent.db"
    task_queue_backend: str = "mock"
    runner_backend: str = "mock"
    run_mode: str = Field(default_factory=lambda: os.getenv("RUN_MODE", "mock"))
    rscript_executable: str = Field(default_factory=lambda: os.getenv("RSCRIPT_EXECUTABLE", "Rscript"))
    docker_r_image: str = Field(
        default_factory=lambda: os.getenv("DOCKER_R_IMAGE", "bioinformatics-agent-r-bulk-rnaseq:0.1")
    )
    docker_executable: str = Field(default_factory=lambda: os.getenv("DOCKER_EXECUTABLE", "docker"))
    docker_workdir: str = Field(default_factory=lambda: os.getenv("DOCKER_WORKDIR", "/workspace"))
    max_preview_rows: int = 5
    low_count_min_total: int = 10


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings
