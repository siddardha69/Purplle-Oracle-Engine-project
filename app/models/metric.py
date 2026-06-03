import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class ZoneMetric(Base):
    """
    Stores pre-calculated analytics hourly summaries.
    Enables low-latency dashboard load without massive database table scanning.
    """
    __tablename__ = "zone_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    store_id = Column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    
    zone_name = Column(String(100), nullable=False, index=True)
    
    # Hour block of aggregation (e.g. 2026-06-01 10:00:00)
    timestamp_hour = Column(DateTime, nullable=False, index=True)
    
    total_visitors = Column(Integer, default=0)
    avg_dwell_time = Column(Float, default=0.0)
    queue_length_avg = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    store = relationship("Store", back_populates="metrics")
