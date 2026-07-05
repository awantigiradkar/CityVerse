import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Database Configuration
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=5432)
    DB_USER: str = Field(default="postgres")
    DB_PASSWORD: str = Field(default="postgres")
    DB_NAME: str = Field(default="cityverse")
    
    # Toggle between SQLite and PostgreSQL
    USE_SQLITE: bool = Field(default=True)

    # API Configuration
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)

    # Gemini LLM API Configuration
    GEMINI_API_KEY: str = Field(default="")

    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO")

    @property
    def database_url(self) -> str:
        """
        Dynamically constructs the database URL. 
        Uses SQLite file-based DB if USE_SQLITE is True, otherwise PostgreSQL.
        """
        if self.USE_SQLITE:
            # Locate db directory in the project root
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_dir = os.path.join(base_dir, "db")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "cityverse.db")
            # Replace Windows backslashes with forward slashes for SQLite connection URI
            formatted_path = db_path.replace("\\", "/")
            return f"sqlite:///{formatted_path}"
            
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Configure Pydantic to read configuration from .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Global settings instance
settings = Settings()