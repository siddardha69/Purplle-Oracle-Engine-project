import os
from loguru import logger
from pipeline.config import pipeline_settings
from pipeline.events import PurplleStoreEvent

class EventEmitter:
    """
    Manages safe, concurrent-resilient appending of structured, validated events
    into flat JSONL files on disk.
    """
    def __init__(self, output_path: str = None):
        self.output_path = output_path or pipeline_settings.OUTPUT_JSONL_PATH
        self._ensure_output_directory()

    def _ensure_output_directory(self):
        """
        Creates target storage folders if missing.
        """
        try:
            parent_dir = os.path.dirname(os.path.abspath(self.output_path))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
                logger.info(f"Target events buffer folder verified: {parent_dir}")
        except Exception as e:
            logger.error(f"Failed to create storage folder for event emitter: {e}")

    def emit(self, event_data: dict) -> bool:
        """
        Validates event dict through PurplleStoreEvent Pydantic schema,
        and appends JSON string directly into events.jsonl file.
        """
        try:
            # 1. Enforce strict Pydantic validations
            event_obj = PurplleStoreEvent(**event_data)
            
            # 2. Extract JSON string line
            line_str = event_obj.to_jsonl_line()
            
            # 3. Append safely to JSONL file on disk
            with open(self.output_path, "a", encoding="utf-8") as f:
                f.write(f"{line_str}\n")
                
            logger.debug(
                f"[EVENT EMITTED] ID: {event_obj.event_id} | Type: {event_obj.event_type} | "
                f"Visitor: {event_obj.visitor_id} | Zone: {event_obj.zone_id}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to emit/validate Purplle Event payload. Error: {e} | Payload: {event_data}")
            return False
            
    def clear_output_file(self):
        """
        Resets output file. Useful before launching a fresh pipeline stream.
        """
        try:
            if os.path.exists(self.output_path):
                os.remove(self.output_path)
                logger.info(f"Cleared existing events log file: {self.output_path}")
        except Exception as e:
            logger.error(f"Failed to clear output file at {self.output_path}: {e}")
