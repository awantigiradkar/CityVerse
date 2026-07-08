"""
Central configuration for Dubai Smart City Digital Twin.

All settings live here. Every other module imports from this file.
Never hardcode paths, URLs, or credentials anywhere else.

How it works:
    1. Pydantic reads values from your .env file automatically
    2. If a value is missing from .env, it uses the default defined here
    3. If a required value is missing and has no default, it crashes
       immediately with a clear error (fail fast = good engineering)

Usage in any other file:
    from dubaidigitaltwin.config import settings
    print(settings.dubai_lat)   # 25.2048
    print(settings.raw_data_dir)  # Path('./data/raw')
"""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central settings class.

    Pydantic automatically:
      - Reads values from the .env file
      - Validates types (e.g. ensures dubai_lat is a float, not a string)
      - Crashes with a clear error if a required field is missing
    """

    # ── Data Directories ──────────────────────────────────────────────────────
    # Path() converts a string like "./data/raw" into a proper path object.
    # On Windows this becomes data\raw, on Linux it stays data/raw.
    # Using Path objects everywhere avoids path separator bugs.
    raw_data_dir: Path = Field(default=Path("./data/raw"))
    synthetic_data_dir: Path = Field(default=Path("./data/synthetic"))
    processed_data_dir: Path = Field(default=Path("./data/processed"))

    # ── Free Public API URLs (no key required) ────────────────────────────────
    openmeteo_base_url: str = "https://api.open-meteo.com/v1"
    openaq_base_url: str = "https://api.openaq.org/v3"

    # ── Dubai Geographic Center ───────────────────────────────────────────────
    # Real GPS coordinates for downtown Dubai (Burj Khalifa area)
    # Source: verified on OpenStreetMap
    dubai_lat: float = 25.2048
    dubai_lon: float = 55.2708

    # ── Reproducibility ───────────────────────────────────────────────────────
    # Fixed seed means: run the synthetic generator today or next year,
    # you get the EXACT same numbers. Critical for reproducible ML experiments.
    random_seed: int = 42

    # ── Database (used in Milestone 3) ────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "dubai_digital_twin"
    postgres_user: str = "dubai_admin"
    postgres_password: str = "changeme"

    # ── MLflow (used in Milestone 5) ──────────────────────────────────────────
    mlflow_tracking_uri: str = "http://localhost:5000"

    # ── Pydantic Configuration ────────────────────────────────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",           # read from .env file
        env_file_encoding="utf-8",
        case_sensitive=False,      # DUBAI_LAT and dubai_lat both work
        extra="ignore",            # ignore unknown keys in .env
    )

    def ensure_directories(self) -> None:
        """
        Create all required data directories if they don't exist.

        Call this once at application startup.

        parents=True  → creates parent folders too (like mkdir -p)
        exist_ok=True → no error if folder already exists
        """
        dirs = [
            self.raw_data_dir,
            self.synthetic_data_dir,
            self.processed_data_dir,
        ]
        for directory in dirs:
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def db_url(self) -> str:
        """
        Build the full PostgreSQL connection string from parts.

        Returns:
            str: e.g. "postgresql://dubai_admin:changeme@localhost:5432/dubai_digital_twin"

        Why a property?
            We never store the full URL in .env because it contains the password.
            We build it on-demand from separate fields. Safer.
        """
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


# ── Singleton Instance ────────────────────────────────────────────────────────
# This single object is shared across the entire application.
# Every module does: from dubaidigitaltwin.config import settings
# They all get the SAME object — not a new one each time.
settings = Settings()