from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field

# ------------------------------------------------------------------------------
# CAMERA SCHEMAS
# ------------------------------------------------------------------------------
class CameraBase(BaseModel):
    name: str = Field(..., examples=["Lipstick Zone CCTV"])
    rtsp_url: str = Field(..., examples=["rtsp://192.168.1.100/stream1"])
    calibration: Optional[Dict[str, Any]] = Field(default=None, examples=[{"homography": [[1,0,0],[0,1,0],[0,0,1]]}])

class CameraCreate(CameraBase):
    store_id: str

class CameraUpdate(BaseModel):
    name: Optional[str] = None
    rtsp_url: Optional[str] = None
    calibration: Optional[Dict[str, Any]] = None

class CameraResponse(CameraBase):
    id: str
    store_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ------------------------------------------------------------------------------
# STORE SCHEMAS
# ------------------------------------------------------------------------------
class StoreBase(BaseModel):
    name: str = Field(..., examples=["Purplle Mall of India"])
    location: str = Field(..., examples=["Noida, Sector 18"])
    layout: Optional[Dict[str, Any]] = Field(
        default=None, 
        examples=[{
            "zones": {
                "lipstick_zone": [[10, 10], [50, 10], [50, 50], [10, 50]],
                "skincare_zone": [[60, 10], [100, 10], [100, 50], [60, 50]]
            }
        }]
    )

class StoreCreate(StoreBase):
    pass

class StoreUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    layout: Optional[Dict[str, Any]] = None

class StoreResponse(StoreBase):
    id: str
    created_at: datetime
    cameras: List[CameraResponse] = []

    model_config = ConfigDict(from_attributes=True)
