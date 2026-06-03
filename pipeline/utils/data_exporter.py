import os
import json
import time
from typing import Dict, Any
import httpx
from configs.settings import settings
from loguru import logger

class DataExporter:
    """
    Exposes unified pipelines to export detected movements events.
    Integrates network fallbacks to local directory caches to prevent data loss.
    """
    def __init__(self):
        self.api_url = f"http://{settings.API_HOST}:{settings.API_PORT}/api/v1/events"
        self.local_cache_dir = settings.EVENT_OUTPUT_DIR
        os.makedirs(self.local_cache_dir, exist_ok=True)

    def export_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Pushes a single structured event row to FastAPI backend server.
        Falls back to write_to_disk on network latency or request failures.
        """
        try:
            logger.debug(f"Attempting to export event: {event_data.get('zone_name')} {event_data.get('event_type')}")
            
            # Synchronous HTTP Post with short connection timeout
            with httpx.Client(timeout=2.0) as client:
                response = client.post(self.api_url, json=event_data)
                
            if response.status_code == 201:
                logger.debug("Successfully exported event to FastAPI API.")
                return True
            else:
                logger.error(f"Inbound API rejection code {response.status_code}. Response: {response.text}")
                
        except Exception as e:
            logger.warning(f"Connection failed to endpoint: {self.api_url}. Caching event locally. Error: {e}")
            
        # Fallback cache write execution
        return self._cache_event_locally(event_data)

    def _cache_event_locally(self, event_data: Dict[str, Any]) -> bool:
        """
        Saves transaction details as JSON rows inside local logs directories.
        """
        try:
            filename = f"event_{int(time.time() * 1000)}.json"
            filepath = os.path.join(self.local_cache_dir, filename)
            
            with open(filepath, "w") as f:
                json.dump(event_data, f, indent=4)
                
            logger.info(f"Buffered event record successfully to: {filepath}")
            return True
        except Exception as ex:
            logger.critical(f"Fatal! Failed to write cache dump to local disk filesystem. Error: {ex}")
            return False
