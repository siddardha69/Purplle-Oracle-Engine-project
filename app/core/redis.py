import redis
from configs.settings import settings
from loguru import logger

class MockPubSub:
    """
    Simulates a Redis Pub/Sub channel listener queue in-memory.
    """
    def __init__(self, mock_redis):
        self.mock_redis = mock_redis
        self.subscribed_channels = []
        import queue
        self._message_queue = queue.Queue()

    def subscribe(self, *channels, **kwargs):
        for channel in channels:
            self.subscribed_channels.append(channel)
            if channel not in self.mock_redis._pubsub_listeners:
                self.mock_redis._pubsub_listeners[channel] = []
            self.mock_redis._pubsub_listeners[channel].append(self)

    def unsubscribe(self, *channels, **kwargs):
        for channel in channels:
            if channel in self.subscribed_channels:
                self.subscribed_channels.remove(channel)
            if channel in self.mock_redis._pubsub_listeners and self in self.mock_redis._pubsub_listeners[channel]:
                self.mock_redis._pubsub_listeners[channel].remove(self)

    def close(self):
        pass

    def get_message(self, ignore_subscribe_messages=True, timeout=1.0):
        try:
            msg = self._message_queue.get_nowait()
            return {"channel": msg[0], "data": msg[1], "type": "message"}
        except Exception:
            return None

class MockRedis:
    """
    Thread-safe in-memory Redis fallback mock.
    Allows local development and rapid testing without a running Redis server.
    """
    def __init__(self):
        self._data = {}
        self._pubsub_listeners = {}
        logger.warning("Initializing In-Memory Mock Redis Fallback.")

    def ping(self):
        return True

    def get(self, key):
        return self._data.get(key)

    def set(self, key, value, ex=None):
        self._data[key] = value
        return True

    def delete(self, *keys):
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                count += 1
        return count

    def hset(self, name, key=None, value=None, mapping=None):
        if name not in self._data:
            self._data[name] = {}
        if mapping:
            self._data[name].update(mapping)
            return len(mapping)
        self._data[name][key] = str(value)
        return 1

    def hget(self, name, key):
        return self._data.get(name, {}).get(key)

    def hgetall(self, name):
        return self._data.get(name, {})

    def zadd(self, name, mapping):
        if name not in self._data:
            self._data[name] = {}
        # ZSET is emulated using keys as items, values as float scores
        for item, score in mapping.items():
            self._data[name][item] = float(score)
        return len(mapping)

    def zscore(self, name, value):
        return self._data.get(name, {}).get(value)

    def zrem(self, name, *values):
        count = 0
        for val in values:
            if name in self._data and val in self._data[name]:
                del self._data[name][val]
                count += 1
        return count

    def pubsub(self):
        return MockPubSub(self)

    def publish(self, channel, message):
        logger.debug(f"[Mock Redis Pub/Sub] Publish to '{channel}': {message}")
        if channel in self._pubsub_listeners:
            for listener in self._pubsub_listeners[channel]:
                listener._message_queue.put((channel, message))
        return 1

class RedisManager:
    """
    Manages the Redis client lifecycle, pooling, and health pinging.
    """
    def __init__(self):
        self.client = None
        self._is_mock = False

    def connect(self):
        try:
            logger.info(f"Connecting to Redis at: {settings.REDIS_URL}")
            # Quick connection timeout check to prevent long hangs on startup
            self.client = redis.Redis.from_url(
                settings.REDIS_URL, 
                decode_responses=True,
                socket_connect_timeout=2.0
            )
            self.client.ping()
            self._is_mock = False
            logger.info("Successfully established connection with Redis.")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"Could not connect to Redis server: {e}. Falling back to Mock Redis.")
            self.client = MockRedis()
            self._is_mock = True

    def get_client(self):
        if not self.client:
            self.connect()
        return self.client

    @property
    def is_mock(self) -> bool:
        return self._is_mock

# Global Redis manager singleton
redis_manager = RedisManager()

def get_redis():
    """
    Dependency helper to acquire the global Redis client.
    """
    return redis_manager.get_client()
