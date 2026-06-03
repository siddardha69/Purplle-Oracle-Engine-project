import uuid
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, HTTPException
from sqlalchemy.orm import Session
from redis import Redis
from app.core.database import get_db
from app.core.redis import get_redis
from app.schemas.event import VisitorEventCreate, VisitorEventResponse
from app.models.event import VisitorEvent
from app.models.session import VisitorSession
from loguru import logger
import json

router = APIRouter()

@router.post(
    "/events", 
    response_model=VisitorEventResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Ingest Real-time Vision Event"
)
def ingest_event(
    event_in: VisitorEventCreate,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis)
):
    """
    Ingest a new spatial transition event (ENTER, EXIT, DWELL) from CCTV pipeline.
    Validates visitor session references and pushes event to Redis Pub/Sub to trigger live dashboard updates.
    """
    start_time = time.perf_counter()
    trace_id = f"TRC-{uuid.uuid4().hex[:6].upper()}"
    
    # 1. Validate associated shopper session (lookup by session UUID or visitor track ID)
    session = db.query(VisitorSession).filter(
        (VisitorSession.id == event_in.session_id) | 
        (VisitorSession.visitor_track_id == event_in.session_id)
    ).first()
    
    if not session:
        # Auto-create visitor session for this track ID to ensure seamless live analytics ingestion!
        try:
            store_id = event_in.metadata.get("store_id") if event_in.metadata else None
            if not store_id:
                store_id = "STORE-DLF-01"
                
            session = VisitorSession(
                id=str(uuid.uuid4()),
                store_id=store_id,
                visitor_track_id=event_in.session_id,
                start_time=event_in.event_timestamp,
                converted=False
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            logger.info(f"Auto-created VisitorSession for tracking ID: {event_in.session_id}")
        except Exception as session_err:
            db.rollback()
            logger.error(f"Failed to auto-create visitor session: {session_err}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"VisitorSession with ID {event_in.session_id} does not exist and could not be auto-created."
            )

    # 2. Record event in PostgreSQL
    db_event = VisitorEvent(
        session_id=session.id,
        camera_id=event_in.camera_id,
        zone_name=event_in.zone_name,
        event_type=event_in.event_type,
        event_timestamp=event_in.event_timestamp,
        duration=event_in.duration,
        metadata=event_in.metadata
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    # 3. Publish to Redis Pub/Sub channel for live Dashboard push
    payload = {
        "event_id": db_event.id,
        "store_id": session.store_id,
        "camera_id": db_event.camera_id,
        "visitor_track_id": session.visitor_track_id,
        "zone_name": db_event.zone_name,
        "event_type": db_event.event_type,
        "duration": db_event.duration,
        "timestamp": db_event.event_timestamp.isoformat()
    }
    
    redis_client.publish(f"store:{session.store_id}:live_events", json.dumps(payload))
    
    # 4. If checkout zone exit is registered and POS purchase details exist, update dwell calculations
    if db_event.zone_name == "checkout_zone" and db_event.event_type == "EXIT":
        session.end_time = db_event.event_timestamp
        session.dwell_time = (session.end_time - session.start_time).total_seconds()
        db.commit()
        
    latency = (time.perf_counter() - start_time) * 1000
    
    # Structured log success
    logger.bind(
        trace_id=trace_id,
        store_id=session.store_id,
        camera_id=db_event.camera_id,
        latency=round(latency, 2),
        event_count=1,
        status_code=201
    ).info(f"Successfully processed event INGESTION. Zone: {db_event.zone_name}, Type: {db_event.event_type}")

    return db_event

@router.get(
    "/events",
    response_model=List[VisitorEventResponse],
    summary="Query Captured Store Events"
)
def get_events(
    store_id: Optional[str] = Query(None, description="Filter events by store"),
    zone_name: Optional[str] = Query(None, description="Filter events by store zone name"),
    db: Session = Depends(get_db)
):
    """
    Retrieves events based on filter criteria.
    """
    query = db.query(VisitorEvent)
    
    if store_id:
        query = query.join(VisitorSession).filter(VisitorSession.store_id == store_id)
    if zone_name:
        query = query.filter(VisitorEvent.zone_name == zone_name)
        
    return query.order_by(VisitorEvent.event_timestamp.desc()).limit(100).all()
