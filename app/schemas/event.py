from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator

class VisitorEventBase(BaseModel):
    zone_name: str = Field(..., examples=["skincare_zone"])
    event_type: str = Field(..., examples=["ENTER"], description="ENTER, EXIT, or DWELL")
    event_timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration: float = Field(default=0.0, description="Dwell duration in seconds, set on EXIT")
    metadata: Optional[Dict[str, Any]] = Field(default=None, examples=[{"bbox": [120, 240, 200, 480], "confidence": 0.89}])

class VisitorEventCreate(VisitorEventBase):
    session_id: str
    camera_id: str

class VisitorEventResponse(VisitorEventBase):
    id: str
    session_id: str
    camera_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def resolve_metadata_clash(cls, data: Any) -> Any:
        # Check if it's an ORM object containing event_metadata
        if not isinstance(data, dict) and hasattr(data, "event_metadata"):
            return {
                "id": data.id,
                "session_id": data.session_id,
                "camera_id": data.camera_id,
                "zone_name": data.zone_name,
                "event_type": data.event_type,
                "event_timestamp": data.event_timestamp,
                "duration": data.duration,
                "created_at": data.created_at,
                "metadata": data.event_metadata
            }
        return data
