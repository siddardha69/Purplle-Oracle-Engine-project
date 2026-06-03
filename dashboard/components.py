import httpx
import websocket
import threading
import json
import queue
import time
from typing import Dict, Any, List, Optional
from configs.settings import settings
from loguru import logger

class APIClient:
    """
    HTTP Client interacting with FastAPI Backend endpoints to pull aggregate analytics.
    """
    def __init__(self, base_url: str = None):
        host = settings.API_HOST if settings.API_HOST != "0.0.0.0" else "localhost"
        self.base_url = base_url or f"http://{host}:{settings.API_PORT}/api/v1"

    def get_health(self) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.get(f"{self.base_url}/health")
                return res.json() if res.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Failed to fetch health check: {e}")
            return {"status": "unhealthy", "error": str(e)}

    def get_metrics(self, store_id: str) -> List[Dict[str, Any]]:
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.base_url}/metrics", params={"store_id": store_id})
                return res.json() if res.status_code == 200 else []
        except Exception as e:
            logger.error(f"Failed to fetch store metrics: {e}")
            return []

    def get_funnel(self, store_id: str) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.base_url}/funnels", params={"store_id": store_id})
                return res.json() if res.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Failed to fetch funnel analytical data: {e}")
            return {}

    def get_heatmap(self, store_id: str) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.base_url}/heatmaps", params={"store_id": store_id})
                return res.json() if res.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Failed to fetch heatmaps coordinates: {e}")
            return {}

    def get_anomalies(self, store_id: str) -> List[Dict[str, Any]]:
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.base_url}/anomalies", params={"store_id": store_id})
                return res.json() if res.status_code == 200 else []
        except Exception as e:
            logger.error(f"Failed to fetch store anomalies: {e}")
            return []

    def get_stream_telemetry(self, store_id: str) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.get(f"{self.base_url}/stream/telemetry", params={"store_id": store_id})
                return res.json() if res.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Failed to fetch stream telemetry: {e}")
            return {}

    def control_stream(self, store_id: str, play: bool) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.post(f"{self.base_url}/stream/control", params={"store_id": store_id, "play": play})
                return res.json() if res.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Failed to trigger stream control: {e}")
            return {}


class LiveWebSocketListener:
    """
    Subscribes to live backend WebSockets in a background daemon thread,
    buffering incoming payloads into a thread-safe Queue.
    """
    def __init__(self, store_id: str):
        self.store_id = store_id
        host = settings.API_HOST if settings.API_HOST != "0.0.0.0" else "localhost"
        self.ws_url = f"ws://{host}:{settings.API_PORT}/ws/store/{store_id}"
        self.event_queue = queue.Queue(maxsize=100)
        self.thread = None
        self.is_running = False

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self._run_socket_loop, daemon=True)
        self.thread.start()
        logger.info(f"WebSocket background listener started on channel: {self.ws_url}")

    def stop(self):
        self.is_running = False
        logger.info("Signaled WebSocket background listener shutdown.")

    def _run_socket_loop(self):
        while self.is_running:
            try:
                # Open socket connection using standard websocket-client library
                ws = websocket.create_connection(self.ws_url, timeout=5.0)
                logger.info("Successfully established socket pipe with API server.")
                
                while self.is_running:
                    try:
                        message = ws.recv()
                        if message:
                            payload = json.loads(message)
                            # Skip PONG heartbeats
                            if payload.get("type") == "PONG":
                                continue
                                
                            # Buffer event queue, drop oldest if full
                            if self.event_queue.full():
                                try:
                                    self.event_queue.get_nowait()
                                except queue.Empty:
                                    pass
                            self.event_queue.put(payload)
                    except websocket.WebSocketTimeoutException:
                        # Send keep-alive ping
                        try:
                            ws.send(json.dumps({"type": "PING"}))
                        except Exception:
                            break
                    except Exception as e:
                        logger.error(f"Error receiving socket payload: {e}")
                        break
                ws.close()
            except Exception as e:
                logger.warning(f"Connection lost to WebSocket server: {e}. Retrying in 3 seconds...")
                time.sleep(3.0)

    def get_new_events(self) -> List[Dict[str, Any]]:
        """
        Pulls all buffered events from queue.
        """
        events = []
        while not self.event_queue.empty():
            try:
                events.append(self.event_queue.get_nowait())
            except queue.Empty:
                break
        return events
