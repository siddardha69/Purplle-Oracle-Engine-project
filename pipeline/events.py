import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict

# Standard Purplle Event Types Literal
EventType = Literal[
    "ENTRY", 
    "EXIT", 
    "ZONE_ENTER", 
    "ZONE_EXIT", 
    "ZONE_DWELL", 
    "BILLING_QUEUE_JOIN", 
    "REENTRY"
]

class PurplleStoreEvent(BaseModel):
    """
    Standard Purplle Event Schema for the Tech Challenge 2026.
    Ensures absolute data integrity and validation checks before logs serialization.
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    store_id: str
    camera_id: str
    visitor_id: str = Field(..., description="Unified persistent shopper ID across track breaks")
    event_type: EventType
    timestamp: str = Field(
        ..., 
        description="ISO 8601 UTC timestamp format: YYYY-MM-DDTHH:MM:SS.SSSZ"
    )
    
    # Optional spatial zone attributes
    zone_id: Optional[str] = Field(default=None)
    dwell_ms: Optional[int] = Field(
        default=None, 
        description="Dwell duration in milliseconds, set on EXIT, ZONE_EXIT, and ZONE_DWELL"
    )
    
    is_staff: bool = Field(default=False)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True
    )

    @field_validator("timestamp")
    @classmethod
    def validate_iso_timestamp(cls, v: str) -> str:
        """
        Verifies that timestamps conform to standard UTC format rules: YYYY-MM-DDTHH:MM:SS.SSSZ.
        """
        try:
            # Enforce check by attempting datetime conversion
            cleaned = v.rstrip('Z')
            if '.' in cleaned:
                dt_part, ms_part = cleaned.split('.')
                # Enforce millisecond truncation if exceeding microsecond lengths
                ms_part = ms_part[:6]
                cleaned = f"{dt_part}.{ms_part}"
                datetime.fromisoformat(cleaned)
            else:
                datetime.fromisoformat(cleaned)
            return v
        except Exception as e:
            raise ValueError(f"Timestamp must conform to valid ISO 8601 formatting. Error: {e}")

    def to_jsonl_line(self) -> str:
        """
        Serializes model parameters into clean single line strings.
        """
        return self.model_dump_json(exclude_none=False)
