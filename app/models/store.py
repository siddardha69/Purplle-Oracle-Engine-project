import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base, engine

# Helper to dynamically select JSONB for Postgres and standard JSON for SQLite
JSON_TYPE = JSONB if engine.dialect.name == "postgresql" else JSON

class Store(Base):
    """
    Represents a physical retail store venue.
    The layout column stores polygonal vectors outlining shopping zones.
    """
    __tablename__ = "stores"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    location = Column(String(200), nullable=False)
    
    # Store layouts: mapping coordinates of zones (e.g. lipstick_zone, skincare_zone, billing_counter)
    layout = Column(JSON_TYPE, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    cameras = relationship("Camera", back_populates="store", cascade="all, delete-orphan")
    sessions = relationship("VisitorSession", back_populates="store", cascade="all, delete-orphan")
    metrics = relationship("ZoneMetric", back_populates="store", cascade="all, delete-orphan")
    anomalies = relationship("Anomaly", back_populates="store", cascade="all, delete-orphan")


class Camera(Base):
    """
    Represents CCTV video inputs mapped to physical layouts.
    Calibration parameters help map 2D bounding boxes to floor plans.
    """
    __tablename__ = "cameras"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    store_id = Column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    rtsp_url = Column(String(500), nullable=False)
    
    # Calibration homography matrix, lens parameters
    calibration = Column(JSON_TYPE, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    store = relationship("Store", back_populates="cameras")
    events = relationship("VisitorEvent", back_populates="camera", cascade="all, delete-orphan")
