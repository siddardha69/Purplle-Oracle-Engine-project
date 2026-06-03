import os
from typing import Tuple, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from configs.settings import settings as global_settings

class PipelineSettings(BaseSettings):
    """
    Unified configuration settings for the Computer Vision Ingestion Pipeline.
    Loads values from environment variables or falls back to sensible retail defaults.
    """
    # File & Path settings
    VIDEO_PATH: str = Field(default="./data/videos/sample_cctv.mp4")
    LAYOUT_PATH: str = Field(default="./data/store_layout.json")
    OUTPUT_JSONL_PATH: str = Field(default="./data/events/events.jsonl")
    
    # Store identity
    STORE_ID: str = Field(default="STORE-DLF-01")
    CAMERA_ID: str = Field(default="CAM-MAIN-01")
    
    # YOLO & Detection Config
    YOLO_MODEL_PATH: str = Field(default="yolov8n.pt")
    CONFIDENCE_THRESHOLD: float = Field(default=0.40)
    
    # Spatial Line Crossing Config (Virtual Entry/Exit Line)
    # Specified as a line segments [(x1, y1), (x2, y2)]
    # Entrance/Exit line across the center of 640x480 frame
    ENTRY_EXIT_LINE: List[Tuple[float, float]] = Field(
        default=[(10.0, 380.0), (630.0, 380.0)],
        description="Coordinates outlining virtual entry/exit gate"
    )
    
    # Direction definitions
    # Crossing from y < line_y to y > line_y represents entry (or vice versa)
    # We define standard vector orientations to evaluate crosses
    ENTRY_DIRECTION_VECTOR: Tuple[float, float] = Field(default=(0.0, 1.0)) # Downwards
    
    # Dwell Tracking Parameters
    DWELL_INTERVAL_MS: int = Field(default=30000, description="Trigger DWELL event every 30s")
    
    # Lightweight ReID Parameters
    REID_TIME_WINDOW_SECONDS: int = Field(default=300, description="Dwell history window to match lost tracks")
    REID_MAX_DISTANCE_PX: float = Field(default=150.0, description="Centroid spatial matching bounds")
    REID_ASPECT_RATIO_TOLERANCE: float = Field(default=0.20, description="Aspect ratio appearance consistency checks")
    
    # Staff/Shopper Classification Parameters
    # (Usually staff wear specific colors or enter specific restricted zones,
    # or have high average dwell times. We check loitering in staff zones or height/width ratios)
    STAFF_DWELL_LIMIT_MS: int = Field(default=1800000, description="If customer dwells for > 30 mins, flag as potential staff")
    
    # Visualizer and Diagnostics Config
    DEBUG_MODE: bool = Field(default=True)
    RENDER_VISUALS: bool = Field(default=True)
    FRAME_SKIP: int = Field(default=0) # 0 means read every frame
    
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate pipeline settings
pipeline_settings = PipelineSettings()
