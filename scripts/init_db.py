import os
import sys
import uuid
import datetime
from pathlib import Path

# Add project root directory to path to enable module imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import Base, engine, SessionLocal
from app.models.store import Store, Camera
from app.models.session import VisitorSession
from app.models.event import VisitorEvent
from app.models.metric import ZoneMetric
from app.models.anomaly import Anomaly
from loguru import logger

def seed_database():
    """
    Auto-generates clean table structures and populates initial mock data.
    """
    logger.info("Initializing database schemas...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Check if database has already been seeded to prevent duplicates
        if db.query(Store).count() > 0:
            logger.info("Database already seeded. Skipping initial seeding sequence.")
            return

        logger.info("Database empty. Starting mock data seeding sequence...")
        
        # 1. Add Store
        store = Store(
            id="STORE-DLF-01",
            name="Purplle Flagship Store (DLF)",
            location="DLF Mall of India, Noida",
            layout={
                "zones": {
                    "store_entrance": [[10, 380], [630, 380], [630, 470], [10, 470]],
                    "makeup_zone": [[10, 10], [300, 10], [300, 180], [10, 180]],
                    "skincare_zone": [[320, 10], [620, 10], [620, 180], [320, 180]],
                    "fragrance_counter": [[10, 200], [300, 200], [300, 350], [10, 350]],
                    "checkout_zone": [[320, 200], [620, 200], [620, 350], [320, 350]]
                }
            }
        )
        db.add(store)
        db.commit()
        logger.info(f"Seeded Store: {store.name}")

        # 2. Add Camera
        camera = Camera(
            id="CAM-MAIN-01",
            store_id=store.id,
            name="Main Entrance & Checkout CCTV",
            rtsp_url="rtsp://localhost:8554/live",
            calibration={
                "homography": [[1.2, 0.1, -10], [-0.05, 1.15, -15], [0.001, 0.002, 1.0]]
            }
        )
        db.add(camera)
        db.commit()
        logger.info(f"Seeded Camera: {camera.name}")

        # 3. Add Visitor Sessions
        # Shopper 1: Converted purchase session
        session_1 = VisitorSession(
            id=str(uuid.uuid4()),
            store_id=store.id,
            visitor_track_id="TRK-0001",
            start_time=datetime.datetime.utcnow() - datetime.timedelta(minutes=45),
            end_time=datetime.datetime.utcnow() - datetime.timedelta(minutes=30),
            dwell_time=900.0,
            converted=True
        )
        # Shopper 2: Loitered, not converted
        session_2 = VisitorSession(
            id=str(uuid.uuid4()),
            store_id=store.id,
            visitor_track_id="TRK-0002",
            start_time=datetime.datetime.utcnow() - datetime.timedelta(minutes=20),
            end_time=None,
            dwell_time=0.0,
            converted=False
        )
        db.add_all([session_1, session_2])
        db.commit()
        logger.info("Seeded Visitor Sessions.")

        # 4. Add Visitor Events
        # Session 1 Transitions
        events = [
            VisitorEvent(
                session_id=session_1.id,
                camera_id=camera.id,
                zone_name="store_entrance",
                event_type="ENTER",
                event_timestamp=session_1.start_time,
                duration=0.0,
                metadata={"bbox": [20, 400, 80, 460]}
            ),
            VisitorEvent(
                session_id=session_1.id,
                camera_id=camera.id,
                zone_name="store_entrance",
                event_type="EXIT",
                event_timestamp=session_1.start_time + datetime.timedelta(seconds=15),
                duration=15.0,
                metadata={"bbox": [40, 410, 100, 470]}
            ),
            VisitorEvent(
                session_id=session_1.id,
                camera_id=camera.id,
                zone_name="makeup_zone",
                event_type="ENTER",
                event_timestamp=session_1.start_time + datetime.timedelta(seconds=30),
                duration=0.0,
                metadata={"bbox": [50, 50, 120, 150]}
            ),
            VisitorEvent(
                session_id=session_1.id,
                camera_id=camera.id,
                zone_name="makeup_zone",
                event_type="EXIT",
                event_timestamp=session_1.start_time + datetime.timedelta(minutes=10),
                duration=570.0,
                metadata={"bbox": [100, 80, 170, 160]}
            ),
            VisitorEvent(
                session_id=session_1.id,
                camera_id=camera.id,
                zone_name="checkout_zone",
                event_type="ENTER",
                event_timestamp=session_1.start_time + datetime.timedelta(minutes=11),
                duration=0.0,
                metadata={"bbox": [340, 210, 410, 310]}
            ),
            VisitorEvent(
                session_id=session_1.id,
                camera_id=camera.id,
                zone_name="checkout_zone",
                event_type="EXIT",
                event_timestamp=session_1.end_time,
                duration=240.0,
                metadata={"bbox": [400, 240, 480, 340]}
            ),
            
            # Session 2 Transitions
            VisitorEvent(
                session_id=session_2.id,
                camera_id=camera.id,
                zone_name="store_entrance",
                event_type="ENTER",
                event_timestamp=session_2.start_time,
                duration=0.0,
                metadata={"bbox": [15, 390, 75, 450]}
            ),
            VisitorEvent(
                session_id=session_2.id,
                camera_id=camera.id,
                zone_name="skincare_zone",
                event_type="ENTER",
                event_timestamp=session_2.start_time + datetime.timedelta(seconds=45),
                duration=0.0,
                metadata={"bbox": [350, 60, 420, 140]}
            )
        ]
        db.add_all(events)
        db.commit()
        logger.info("Seeded Visitor Movement Transition Events.")

        # 5. Add pre-calculated hourly Analytics Metrics
        metric_1 = ZoneMetric(
            store_id=store.id,
            zone_name="makeup_zone",
            timestamp_hour=datetime.datetime.utcnow().replace(minute=0, second=0, microsecond=0),
            total_visitors=145,
            avg_dwell_time=125.4,
            queue_length_avg=0.0
        )
        metric_2 = ZoneMetric(
            store_id=store.id,
            zone_name="skincare_zone",
            timestamp_hour=datetime.datetime.utcnow().replace(minute=0, second=0, microsecond=0),
            total_visitors=98,
            avg_dwell_time=210.8,
            queue_length_avg=0.0
        )
        metric_3 = ZoneMetric(
            store_id=store.id,
            zone_name="checkout_zone",
            timestamp_hour=datetime.datetime.utcnow().replace(minute=0, second=0, microsecond=0),
            total_visitors=62,
            avg_dwell_time=185.0,
            queue_length_avg=2.4
        )
        db.add_all([metric_1, metric_2, metric_3])
        db.commit()
        logger.info("Seeded Pre-Aggregated Zone Metrics.")

        # 6. Add active Operational Anomalies
        anomaly = Anomaly(
            store_id=store.id,
            session_id=session_2.id,
            anomaly_type="SUSPICIOUS_DWELL",
            severity="WARNING",
            description="Visitor TRK-0002 has loitered inside Skincare Zone for more than 15 minutes.",
            detected_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=5),
            metadata={"current_dwell_duration": 1150.0}
        )
        db.add(anomaly)
        db.commit()
        logger.info("Seeded Operational Warnings & Anomalies.")

        # 7. Ingest POS Transactions & Correlate Conversions
        from app.services.pos_ingestion import POSIngestionService
        from app.services.pos_correlation import POSCorrelationService
        
        pos_ingestion = POSIngestionService(db=db)
        pos_ingestion.ingest_pos_csv()
        
        pos_correlation = POSCorrelationService(db=db)
        pos_correlation.correlate_sessions_to_transactions(store.id)

        logger.info("Database seeded successfully with premium retail mocks.")
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
