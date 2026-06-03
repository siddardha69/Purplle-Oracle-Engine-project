import time
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.analytics import AnalyticsService
from app.services.store_metrics import StoreMetricsService
from app.services.visitor_analytics import VisitorAnalyticsService
from app.schemas.metric import MetricSummaryResponse, StoreAnalyticsResponse, VisitorSessionAnalyticsResponse
from loguru import logger

router = APIRouter()

@router.get(
    "/metrics",
    response_model=List[MetricSummaryResponse],
    summary="Query Store Zone Analytics"
)
def get_store_metrics(
    store_id: str = Query(..., description="ID of target store"),
    hours_back: int = Query(24, description="Filter metrics window"),
    db: Session = Depends(get_db)
):
    """
    Returns total shopper volumes and average zone dwell times.
    Utilized heavily to update operational dashboard KPI modules.
    """
    start_time = time.perf_counter()
    trace_id = f"TRC-{uuid.uuid4().hex[:6].upper()}"
    
    end_time = datetime.utcnow()
    start_filter = end_time - timedelta(hours=hours_back)
    
    analytics_svc = AnalyticsService(db=db)
    metrics = analytics_svc.get_zone_analytics(store_id, start_filter, end_time)
    
    latency = (time.perf_counter() - start_time) * 1000
    
    logger.bind(
        trace_id=trace_id,
        store_id=store_id,
        latency=round(latency, 2),
        event_count=len(metrics),
        status_code=200
    ).info(f"Retrieved metrics summary for store: {store_id}. Window: last {hours_back} hours.")
    
    return metrics


@router.get(
    "/analytics/store",
    response_model=StoreAnalyticsResponse,
    summary="Fetch Storefront Performance Analytics"
)
def get_store_analytics(
    store_id: str = Query(..., description="ID of store to query"),
    hours_back: int = Query(24, description="Filter metrics window"),
    db: Session = Depends(get_db)
):
    """
    Computes retail performance metrics: Footfall totals, average Completed dwells,
    conversion ratios, return shopping rates, and peak storefront hours.
    """
    start_time = time.perf_counter()
    trace_id = f"TRC-{uuid.uuid4().hex[:6].upper()}"
    
    store_svc = StoreMetricsService(db=db)
    summary = store_svc.generate_store_summary(store_id, hours_back)
    
    latency = (time.perf_counter() - start_time) * 1000
    
    logger.bind(
        trace_id=trace_id,
        store_id=store_id,
        latency=round(latency, 2),
        status_code=200
    ).info(f"Retrieved storefront performance metrics for store: {store_id}")
    
    return summary


@router.get(
    "/analytics/visitors",
    response_model=List[VisitorSessionAnalyticsResponse],
    summary="Batch Visitor Session Sequence Analytics"
)
def get_visitor_session_analytics(
    store_id: str = Query(..., description="ID of store to query"),
    db: Session = Depends(get_db)
):
    """
    Generates granular session sequence analytics across all visitor trajectories.
    Identifies entry/exit times, zones traversed, and cumulative dwells.
    """
    start_time = time.perf_counter()
    trace_id = f"TRC-{uuid.uuid4().hex[:6].upper()}"
    
    visitor_svc = VisitorAnalyticsService(db=db)
    sessions = visitor_svc.analyze_all_active_sessions(store_id)
    
    latency = (time.perf_counter() - start_time) * 1000
    
    logger.bind(
        trace_id=trace_id,
        store_id=store_id,
        latency=round(latency, 2),
        event_count=len(sessions),
        status_code=200
    ).info(f"Retrieved session sequence analytics for store: {store_id}")
    
    return sessions
