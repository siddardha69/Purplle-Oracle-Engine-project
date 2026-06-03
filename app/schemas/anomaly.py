from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator

class AnomalyBase(BaseModel):
    anomaly_type: str = Field(..., examples=["QUEUE_BOTTLENECK"])
    severity: str = Field(..., examples=["WARNING"], description="INFO, WARNING, CRITICAL")
    description: str = Field(..., examples=["Checkout 1 queue exceeds 5 people for more than 3 minutes"])
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default=None, examples=[{"active_queue_count": 6}])

class AnomalyCreate(AnomalyBase):
    store_id: str
    session_id: Optional[str] = None

class AnomalyResponse(AnomalyBase):
    id: str
    store_id: str
    session_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def resolve_metadata_clash(cls, data: Any) -> Any:
        # Check if it's an ORM object containing anomaly_metadata
        if not isinstance(data, dict) and hasattr(data, "anomaly_metadata"):
            return {
                "id": data.id,
                "store_id": data.store_id,
                "session_id": data.session_id,
                "anomaly_type": data.anomaly_type,
                "severity": data.severity,
                "description": data.description,
                "detected_at": data.detected_at,
                "metadata": data.anomaly_metadata
            }
        return data
