import time
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.anomaly import AnomalyResponse, AnomalyCreate
from app.models.anomaly import Anomaly
from loguru import logger

router = APIRouter()

@router.get(
    "/anomalies",
    response_model=List[AnomalyResponse],
    summary="Query Triggered Store Anomalies"
)
def get_anomalies(
    store_id: str = Query(..., description="ID of target store"),
    severity: Optional[str] = Query(None, description="Filter: INFO, WARNING, CRITICAL"),
    db: Session = Depends(get_db)
):
    """
    Returns high-priority spatial and operational anomalies like excessive queues, 
    shoppers lingering in high-value cosmetics counters, or sudden movement patterns.
    """
    start_time = time.perf_counter()
    trace_id = f"TRC-{uuid.uuid4().hex[:6].upper()}"
    
    query = db.query(Anomaly).filter(Anomaly.store_id == store_id)
    if severity:
        query = query.filter(Anomaly.severity == severity)
        
    anomalies = query.order_by(Anomaly.detected_at.desc()).limit(50).all()
    
    # Fallback mock anomalies if database is clean
    if not anomalies:
        logger.debug("Database empty. Supplying mock warning thresholds.")
        import datetime
        anomalies = [
            Anomaly(
                id=str(uuid.uuid4()),
                store_id=store_id,
                anomaly_type="QUEUE_BOTTLENECK",
                severity="WARNING",
                description="Billing counter queue exceeds 5 people (Active count: 7)",
                detected_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=12)
            ),
            Anomaly(
                id=str(uuid.uuid4()),
                store_id=store_id,
                anomaly_type="UNUSUAL_DWELL",
                severity="INFO",
                description="Shopper TRK-894 dwell duration in high-value zone exceeds 8 minutes",
                detected_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=30)
            )
        ]
        
    latency = (time.perf_counter() - start_time) * 1000
    
    # Structured log
    logger.bind(
        trace_id=trace_id,
        store_id=store_id,
        camera_id="ALL",
        latency=round(latency, 2),
        event_count=len(anomalies),
        status_code=200
    ).info(f"Retrieved active anomaly list for store: {store_id}. Count: {len(anomalies)}.")
    
    return anomalies

@router.post(
    "/anomalies",
    response_model=AnomalyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest Store Anomaly Event"
)
def create_anomaly(
    anomaly_in: AnomalyCreate,
    db: Session = Depends(get_db)
):
    """
    Ingests and persists a new anomaly event triggered by background CV models or dashboards.
    """
    from app.services.websocket_manager import ws_manager
    from app.models.session import VisitorSession
    
    # Try to resolve track ID to session
    session_id = anomaly_in.session_id
    if session_id:
        session = db.query(VisitorSession).filter(
            (VisitorSession.id == session_id) |
            (VisitorSession.visitor_track_id == session_id)
        ).first()
        if session:
            session_id = session.id
            
    anomaly = Anomaly(
        id=str(uuid.uuid4()),
        store_id=anomaly_in.store_id,
        session_id=session_id,
        anomaly_type=anomaly_in.anomaly_type,
        severity=anomaly_in.severity,
        description=anomaly_in.description,
        detected_at=anomaly_in.detected_at,
        anomaly_metadata=anomaly_in.metadata
    )
    db.add(anomaly)
    db.commit()
    db.refresh(anomaly)
    
    # Broadcast to dashboard real-time channels via WebSockets
    ws_event = {
        "event_type": "ANOMALY",
        "anomaly_type": anomaly.anomaly_type,
        "severity": anomaly.severity,
        "description": anomaly.description,
        "timestamp": anomaly.detected_at.isoformat(),
        "store_id": anomaly.store_id,
        "metadata": anomaly.anomaly_metadata
    }
    
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(ws_manager.broadcast_to_store(anomaly.store_id, ws_event))
    except Exception as ws_err:
        logger.error(f"Failed to broadcast anomaly over WS: {ws_err}")
        
    return anomaly

