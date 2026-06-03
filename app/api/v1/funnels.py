import time
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.funnel_analytics import FunnelAnalyticsService
from app.schemas.metric import FunnelResponse
from loguru import logger

router = APIRouter()

@router.get(
    "/funnels",
    response_model=FunnelResponse,
    summary="Fetch Store Purchase Conversion Funnel"
)
def get_store_funnel(
    store_id: str = Query(..., description="ID of store to generate conversion funnel for"),
    db: Session = Depends(get_db)
):
    """
    Computes shopping progression ratios: Store entrance -> Zone exploration -> Checkout -> Sale execution.
    Identifies friction bottlenecks and low conversion zones.
    """
    start_time = time.perf_counter()
    trace_id = f"TRC-{uuid.uuid4().hex[:6].upper()}"
    
    funnel_svc = FunnelAnalyticsService(db=db)
    funnel = funnel_svc.calculate_funnel(store_id)
    
    # Map fields to match schema response model names exactly
    mapped_funnel = {
        "store_id": funnel["store_id"],
        "steps": [
            {
                "step_number": idx + 1,
                "zone_name": step["step"],
                "visitors": step["visitors"],
                "conversion_rate": step["conversion_rate"]
            }
            for idx, step in enumerate(funnel["steps"])
        ],
        "total_conversion_rate": funnel["overall_conversion_rate"]
    }
    
    latency = (time.perf_counter() - start_time) * 1000
    
    # Structured log
    logger.bind(
        trace_id=trace_id,
        store_id=store_id,
        latency=round(latency, 2),
        event_count=len(mapped_funnel.get("steps", [])),
        status_code=200
    ).info(f"Retrieved conversion funnel for store: {store_id}.")
    
    return mapped_funnel
