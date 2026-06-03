import os
from pathlib import Path
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get workspace root path
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """
    Central application settings loader using Pydantic V2.
    Validates types, enforces rules, and reads values from environmental variables or .env files.
    """
    
    # Project Settings
    PROJECT_NAME: str = Field(default="Purplle Store Intelligence System")
    VERSION: str = Field(default="1.0.0")
    ENVIRONMENT: Literal["development", "testing", "production"] = Field(default="development")
    
    # API Router Settings
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    SECRET_KEY: str = Field(default="supersecretpurpllestoreintelligencekey")
    
    # Database Settings
    # Enforces standard SQL connection strings. Falls back to SQLite if Postgres is unavailable.
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/store_intelligence"
    )
    
    # Redis Cache and Event Pipeline Broker Settings
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    
    # Machine Learning / Computer Vision Settings
    MODEL_PATH: str = Field(default="yolov8n.pt")
    VIDEO_DIR: str = Field(default="./data/videos")
    LAYOUT_DIR: str = Field(default="./data/layouts")
    POS_DIR: str = Field(default="./data/pos")
    OUTPUT_DIR: str = Field(default="./data/outputs")
    VALIDATION_DIR: str = Field(default="./data/validation")
    EVENT_OUTPUT_DIR: str = Field(default="./data/events")
    
    # Structured Logging settings
    LOG_LEVEL: Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    LOG_TO_FILE: bool = Field(default=True)
    LOG_FILE_PATH: str = Field(default="./logs/store_intelligence.log")
    
    # Enable reading from .env file
    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("VIDEO_DIR", "LAYOUT_DIR", "POS_DIR", "OUTPUT_DIR", "VALIDATION_DIR", "EVENT_OUTPUT_DIR", "LOG_FILE_PATH")
    @classmethod
    def ensure_directories_exist(cls, v: str) -> str:
        """
        Ensures filesystem folders for local streams, export caches, and log files are ready.
        """
        path = Path(v)
        if path.suffix:  # It's a file path (like logs/store_intelligence.log)
            path.parent.mkdir(parents=True, exist_ok=True)
        else:  # It's a folder path
            path.mkdir(parents=True, exist_ok=True)
        return v

# Instantiate global settings singleton
settings = Settings()
