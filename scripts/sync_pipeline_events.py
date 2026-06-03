import os
import sys
import json
from datetime import datetime
from pathlib import Path
from loguru import logger

# Add project root directory to path to enable module imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models.store import Store
from app.models.session import VisitorSession
from app.models.event import VisitorEvent
from app.services.pos_correlation import POSCorrelationService

def sync_events():
    """
    Parses flat JSONL tracking logs and populates the SQLite database.
    """
    jsonl_path = Path("./data/events/events.jsonl")
    if not jsonl_path.exists():
        logger.error(f"Flat events log file not found at: {jsonl_path}")
        return
        
    db = SessionLocal()
    
    try:
        # Verify target store DLF exists
        store = db.query(Store).filter(Store.id == "STORE-DLF-01").first()
        if not store:
            logger.error("Seeded store 'STORE-DLF-01' missing. Run 'python scripts/init_db.py' first.")
            return
            
        logger.info("Starting synchronization of tracking events to relational database...")
        
        sessions_created = 0
        events_created = 0
        
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    raw_event = json.loads(line)
                    
                    visitor_track_id = raw_event["visitor_id"]
                    event_type = raw_event["event_type"]
                    timestamp_str = raw_event["timestamp"]
                    zone_id = raw_event.get("zone_id")
                    dwell_ms = raw_event.get("dwell_ms")
                    confidence = raw_event.get("confidence", 1.0)
                    metadata = raw_event.get("metadata", {})
                    
                    # 1. Fetch or create VisitorSession
                    session = db.query(VisitorSession).filter(
                        VisitorSession.store_id == store.id,
                        VisitorSession.visitor_track_id == visitor_track_id
                    ).first()
                    
                    if not session:
                        # Parse timestamp offset to datetime
                        cleaned_ts = timestamp_str.replace("Z", "")
                        dt_val = datetime.fromisoformat(cleaned_ts)
                        
                        session = VisitorSession(
                            store_id=store.id,
                            visitor_track_id=visitor_track_id,
                            start_time=dt_val,
                            converted=False
                        )
                        db.add(session)
                        db.flush()  # Populates session.id
                        sessions_created += 1
                        
                    # 2. Check and sync VisitorEvent
                    event_id = raw_event.get("event_id")
                    existing_event = db.query(VisitorEvent).filter(VisitorEvent.id == event_id).first() if event_id else None
                    
                    if not existing_event:
                        cleaned_ts = timestamp_str.replace("Z", "")
                        dt_val = datetime.fromisoformat(cleaned_ts)
                        
                        # Calculate duration in float seconds
                        duration_s = float(dwell_ms) / 1000.0 if dwell_ms else 0.0
                        
                        new_event = VisitorEvent(
                            id=event_id,
                            session_id=session.id,
                            camera_id=raw_event["camera_id"],
                            zone_name=zone_id or "store_entrance",
                            event_type=event_type,
                            event_timestamp=dt_val,
                            duration=duration_s,
                            event_metadata=metadata
                        )
                        db.add(new_event)
                        events_created += 1
                        
                except Exception as line_err:
                    logger.error(f"Error parsing tracking line: {line_err}")
                    
        db.commit()
        logger.info(f"Database Ingest finalized. Synced: {sessions_created} Sessions | {events_created} Events.")
        
        # 3. Trigger Transaction correlations sweeps
        pos_correlator = POSCorrelationService(db=db)
        logger.info("Executing POS Transactions Correlation sweep on real tracking logs...")
        pos_correlator.correlate_sessions_to_transactions(store.id)
        
    except Exception as e:
        logger.error(f"Synchronizer execution failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    sync_events()
