from sqlalchemy.orm import Session
from redis import Redis
from app.core.database import get_db_context
from app.core.redis import get_redis

class BaseService:
    """
    Base service wrapper injecting PostgreSQL and Redis connection dependencies.
    Ensures easy database interactions with automated session handling capability.
    """
    def __init__(self, db: Session = None, redis_client: Redis = None):
        self._db = db
        self._redis = redis_client or get_redis()

    @property
    def db(self) -> Session:
        """
        Returns active database session or spawns a thread-safe context session.
        """
        if self._db is not None:
            return self._db
        # Spawn session if not already available
        self._db = next(get_db_context())
        return self._db

    @property
    def redis(self) -> Redis:
        return self._redis
