from app.core.database import Base
from app.models.store import Store, Camera
from app.models.session import VisitorSession
from app.models.event import VisitorEvent
from app.models.metric import ZoneMetric
from app.models.anomaly import Anomaly
from app.models.pos_transaction import POSTransaction

# All tables list to export easily for alembic migration discoveries
__all__ = [
    "Base",
    "Store",
    "Camera",
    "VisitorSession",
    "VisitorEvent",
    "ZoneMetric",
    "Anomaly",
    "POSTransaction"
]
