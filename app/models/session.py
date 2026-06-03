import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class VisitorSession(Base):
    """
    Groups individual visitor temporal traces inside a store.
    Captures exact time vectors, checkout interactions, and conversion success.
    """
    __tablename__ = "visitor_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    store_id = Column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    
    # ID assigned by the multi-object tracking pipeline
    visitor_track_id = Column(String(100), nullable=False, index=True)
    
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    
    # Total occupancy time in seconds
    dwell_time = Column(Float, default=0.0)
    
    # Flags whether this session matched a checkout transaction in pos_transactions.csv
    converted = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    store = relationship("Store", back_populates="sessions")
    events = relationship("VisitorEvent", back_populates="session", cascade="all, delete-orphan")
    anomalies = relationship("Anomaly", back_populates="session", cascade="all, delete-orphan")
