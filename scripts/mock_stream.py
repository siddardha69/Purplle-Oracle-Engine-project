import os
import sys
import time
import random
import requests
from datetime import datetime, timedelta
from pathlib import Path

# Add project root directory to path to enable module imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models.store import Store, Camera
from app.models.session import VisitorSession
from configs.settings import settings
from loguru import logger

def simulate_pipeline_ingestion():
    """
    Continuously streams synthetic shopper transition events to the FastAPI backend,
    animating live telemetry indicators on dashboards in real-time.
    """
    logger.info("Initializing CCTV Edge Processor stream simulation...")
    api_url = f"http://127.0.0.1:{settings.API_PORT}/api/v1"
    
    # 1. Verify API server liveness
    try:
        res = requests.get(f"{api_url}/health", timeout=2.0)
        if res.status_code != 200:
            logger.error("API server offline. Please launch the API server before starting the simulator.")
            return
    except Exception as e:
        logger.error(f"Cannot connect to API server: {e}. Start the backend server first!")
        return

    db = SessionLocal()
    
    try:
        # Retrieve or seed store metadata
        store = db.query(Store).filter(Store.id == "STORE-DLF-01").first()
        if not store:
            logger.error("Database has not been seeded yet. Run 'python scripts/init_db.py' first!")
            return
            
        camera = db.query(Camera).filter(Camera.store_id == store.id).first()
        if not camera:
            logger.error("No cameras found associated with store.")
            return
            
        logger.info(f"Target Store: {store.name} | Camera: {camera.name}")
        logger.info("Connection confirmed. Streaming mock events to backend. Ctrl+C to terminate.")
        
        # Store tracking parameters
        active_shoppers = {} # track_id -> (session_uuid, current_zone_idx)
        active_entry_times = {} # track_id -> unix_time
        
        zones = ["store_entrance", "makeup_zone", "skincare_zone", "fragrance_counter", "checkout_zone"]
        track_counter = 100
        
        while True:
            current_time = datetime.utcnow()
            
            # 1. Spawn a new shopper (25% chance per tick, cap at 5 active)
            if len(active_shoppers) < 5 and random.random() < 0.25:
                track_counter += 1
                track_id = f"TRK-{track_counter:04d}"
                
                # Create a persistent session in the database
                session = VisitorSession(
                    store_id=store.id,
                    visitor_track_id=track_id,
                    start_time=current_time,
                    converted=False
                )
                db.add(session)
                db.commit()
                db.refresh(session)
                
                # Start them at entrance
                active_shoppers[track_id] = (session.id, 0)
                active_entry_times[track_id] = time.time()
                
                # Post ENTER event
                event_payload = {
                    "session_id": session.id,
                    "camera_id": camera.id,
                    "zone_name": "store_entrance",
                    "event_type": "ENTER",
                    "duration": 0.0,
                    "metadata": {"bbox": [20, 400, 80, 460]}
                }
                requests.post(f"{api_url}/events", json=event_payload, timeout=1.0)
                logger.info(f"Shopper {track_id} entered store.")
                
            # 2. Process active shoppers (move or checkout)
            shoppers_to_remove = []
            for track_id, (session_uuid, current_zone_idx) in list(active_shoppers.items()):
                dwell = time.time() - active_entry_times[track_id]
                
                # If they have spent some time in the current zone, trigger a transition
                if dwell > random.randint(4, 12):
                    prev_zone = zones[current_zone_idx]
                    
                    # Send EXIT event for previous zone
                    exit_payload = {
                        "session_id": session_uuid,
                        "camera_id": camera.id,
                        "zone_name": prev_zone,
                        "event_type": "EXIT",
                        "duration": round(dwell, 2),
                        "metadata": {"bbox": [50, 50, 100, 100]}
                    }
                    requests.post(f"{api_url}/events", json=exit_payload, timeout=1.0)
                    
                    # Determine next zone
                    if current_zone_idx == len(zones) - 1:
                        # They are in checkout. They leave the store now.
                        shoppers_to_remove.append(track_id)
                        logger.info(f"Shopper {track_id} completed billing and left store.")
                        
                        # Randomly mark as converted (purchase completed in POS)
                        if random.random() < 0.6:
                            session = db.query(VisitorSession).filter(VisitorSession.id == session_uuid).first()
                            if session:
                                session.converted = True
                                db.commit()
                                logger.info(f"Shopper {track_id} purchase recorded in POS. Conversion successful!")
                    else:
                        # Move to next logical zone (or skip around randomly)
                        next_zone_idx = current_zone_idx + random.choice([1, 2])
                        # Bound within limits
                        next_zone_idx = min(next_zone_idx, len(zones) - 1)
                        
                        next_zone = zones[next_zone_idx]
                        active_shoppers[track_id] = (session_uuid, next_zone_idx)
                        active_entry_times[track_id] = time.time()
                        
                        # Send ENTER event for next zone
                        enter_payload = {
                            "session_id": session_uuid,
                            "camera_id": camera.id,
                            "zone_name": next_zone,
                            "event_type": "ENTER",
                            "duration": 0.0,
                            "metadata": {"bbox": [150, 150, 200, 200]}
                        }
                        requests.post(f"{api_url}/events", json=enter_payload, timeout=1.0)
                        logger.info(f"Shopper {track_id} transitioned from '{prev_zone}' to '{next_zone}'.")
                        
            # Clean up exited shoppers
            for track_id in shoppers_to_remove:
                active_shoppers.pop(track_id, None)
                active_entry_times.pop(track_id, None)
                
            # Loop delay
            time.sleep(2.0)
            
    except KeyboardInterrupt:
        logger.info("Ingestion simulator manual termination.")
    finally:
        db.close()

if __name__ == "__main__":
    simulate_pipeline_ingestion()
