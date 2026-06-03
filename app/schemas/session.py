from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class VisitorSessionBase(BaseModel):
    visitor_track_id: str = Field(..., examples=["TRK-1002"])
    start_time: datetime
    end_time: Optional[datetime] = None
    dwell_time: float = Field(default=0.0, description="Dwell time in seconds")
    converted: bool = Field(default=False)

class VisitorSessionCreate(BaseModel):
    store_id: str
    visitor_track_id: str
    start_time: Optional[datetime] = None

class VisitorSessionUpdate(BaseModel):
    end_time: Optional[datetime] = None
    dwell_time: Optional[float] = None
    converted: Optional[bool] = None

class VisitorSessionResponse(VisitorSessionBase):
    id: str
    store_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
