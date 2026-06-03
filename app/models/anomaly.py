import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base, engine

# Helper to dynamically select JSONB for Postgres and standard JSON for SQLite
JSON_TYPE = JSONB if engine.dialect.name == "postgresql" else JSON

class Anomaly(Base):
    """
    Stores system anomalies triggered by temporal/spatial pattern analysis.
    Identifies high checkout queues, high dwell in restricted areas, or suspicious loitering.
    """
    __tablename__ = "anomalies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    store_id = Column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    
    # Associated shopper track session if applicable
    session_id = Column(String(36), ForeignKey("visitor_sessions.id", ondelete="SET NULL"), nullable=True)
    
    # e.g., QUEUE_BOTTLENECK, LOITERING, UNUSUAL_DWELL, SHOPLIFT_SUSPICION
    anomaly_type = Column(String(100), nullable=False, index=True)
    
    # Severity levels: INFO, WARNING, CRITICAL
    severity = Column(String(50), nullable=False)
    description = Column(String(500), nullable=False)
    
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Context-specific event payloads
    anomaly_metadata = Column("metadata", JSON_TYPE, nullable=True)

    # Relationships
    store = relationship("Store", back_populates="anomalies")
    session = relationship("VisitorSession", back_populates="anomalies")
