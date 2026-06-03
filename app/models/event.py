import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base, engine

# Helper to dynamically select JSONB for Postgres and standard JSON for SQLite
JSON_TYPE = JSONB if engine.dialect.name == "postgresql" else JSON

class VisitorEvent(Base):
    """
    Stores structured spatial events emitted by the Computer Vision tracking pipeline.
    Represents zone transitions like ENTER and EXIT.
    """
    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("visitor_sessions.id", ondelete="CASCADE"), nullable=False)
    camera_id = Column(String(36), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False)
    
    # Store zones outlined in store_layout.json (e.g. skin_care, billing, entrance)
    zone_name = Column(String(100), nullable=False, index=True)
    
    # Event types: ENTER, EXIT, DWELL
    event_type = Column(String(50), nullable=False)
    event_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Duration within the zone (calculated during EXIT events)
    duration = Column(Float, default=0.0)
    
    # Detailed metadata (e.g., box coordinate matrix, prediction scores, speed vector)
    event_metadata = Column("metadata", JSON_TYPE, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("VisitorSession", back_populates="events")
    camera = relationship("Camera", back_populates="events")
