import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class POSTransaction(Base):
    """
    Stores cash registry transaction logs imported from pos_transactions.csv.
    Used for automated conversions correlation.
    """
    __tablename__ = "pos_transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String(100), unique=True, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    
    store_id = Column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    billing_counter = Column(String(50), nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    store = relationship("Store")
