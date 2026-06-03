import time
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.heatmap import HeatmapService
from app.schemas.metric import HeatmapResponse
from loguru import logger

router = APIRouter()

@router.get(
    "/heatmaps",
    response_model=HeatmapResponse,
    summary="Fetch Spatial coordinate density map"
)
def get_store_heatmap(
    store_id: str = Query(..., description="Target Store ID"),
    camera_id: Optional[str] = Query(None, description="Filter for specific camera sensor"),
    db: Session = Depends(get_db)
):
    """
    Retrieves dense spatial grids to visualize shopping density clusters.
    Used by frontends to plot colors overlay on store blueprints.
    """
    start_time = time.perf_counter()
    trace_id = f"TRC-{uuid.uuid4().hex[:6].upper()}"
    
    heatmap_svc = HeatmapService(db=db)
    heatmap = heatmap_svc.generate_store_heatmap(store_id)
    
    latency = (time.perf_counter() - start_time) * 1000
    
    # Structured log
    logger.bind(
        trace_id=trace_id,
        store_id=store_id,
        camera_id=camera_id or "ALL",
        latency=round(latency, 2),
        event_count=len(heatmap.get("hotspots", [])),
        status_code=200
    ).info(f"Retrieved coordinate heatmap for store: {store_id}.")
    
    # Map key list 'hotspots' to 'points' to conform to schemas response model
    return {
        "store_id": store_id,
        "camera_id": camera_id,
        "points": [
            {"x": pt["x"], "y": pt["y"], "intensity": pt["intensity"]}
            for pt in heatmap["hotspots"]
        ]
    }
