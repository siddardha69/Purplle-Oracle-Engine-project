from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field

class ZoneMetricBase(BaseModel):
    zone_name: str = Field(..., examples=["perfume_zone"])
    timestamp_hour: datetime
    total_visitors: int = Field(default=0)
    avg_dwell_time: float = Field(default=0.0, description="Average dwell time in seconds")
    queue_length_avg: float = Field(default=0.0)

class ZoneMetricResponse(ZoneMetricBase):
    id: str
    store_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ------------------------------------------------------------------------------
# ANALYTICS QUERY SCHEMAS
# ------------------------------------------------------------------------------
class MetricSummaryResponse(BaseModel):
    store_id: str
    zone_name: str
    total_footfall: int
    avg_dwell_seconds: float
    busy_hours: List[int]

class FunnelStep(BaseModel):
    step_number: int
    zone_name: str
    visitors: int
    conversion_rate: float = Field(..., description="Percentage of visitors from the previous step")

class FunnelResponse(BaseModel):
    store_id: str
    steps: List[FunnelStep]
    total_conversion_rate: float = Field(..., description="Percentage of first step visitors that checked out")

class HeatmapGridCell(BaseModel):
    x: int
    y: int
    intensity: float = Field(..., description="Aggregated coordinate occurrence count or weight")

class HeatmapResponse(BaseModel):
    store_id: str
    camera_id: Optional[str] = None
    points: List[HeatmapGridCell]

# ------------------------------------------------------------------------------
# RETAIL INTELLIGENCE LAYER SCHEMAS
# ------------------------------------------------------------------------------
class ZonePopularityItem(BaseModel):
    zone_name: str
    total_visits: int
    avg_dwell_seconds: float

class StoreAnalyticsResponse(BaseModel):
    store_id: str
    timestamp: str
    footfall_total: int
    active_occupancy: int
    avg_dwell_minutes: float
    peak_hours: List[int]
    conversion_rate_percentage: float
    reentry_rate_percentage: float
    zone_popularity: List[ZonePopularityItem]

class VisitorSessionAnalyticsResponse(BaseModel):
    session_id: str
    visitor_track_id: str
    entry_time: datetime
    exit_time: Optional[datetime] = None
    visit_duration: float
    zones_visited: List[str]
    dwell_per_zone: Dict[str, float]
    session_length: float
    checkout_reached: bool
    converted: bool

