import os
import time
from typing import List, Dict, Any, Tuple
from loguru import logger
from pipeline.config import pipeline_settings

# Try loading Ultralytics YOLO safely
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("Ultralytics library missing. Detection running in simulated mode.")

class PersonDetector:
    """
    Wrapper for YOLOv8 object detection targeted at human person shapes class tracking.
    """
    def __init__(self, model_path: str = None, conf_threshold: float = None):
        self.model_path = model_path or pipeline_settings.YOLO_MODEL_PATH
        self.conf_threshold = conf_threshold if conf_threshold is not None else pipeline_settings.CONFIDENCE_THRESHOLD
        self.model = None
        self.is_simulation = True
        
        if YOLO_AVAILABLE:
            try:
                # Force checking weights existence before loading models
                logger.info(f"Loading YOLOv8 network weights from: {self.model_path}")
                self.model = YOLO(self.model_path)
                self.is_simulation = False
                logger.info("YOLOv8 person detector initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to load YOLOv8 model: {e}. Falling back to simulation.")
        else:
            logger.info("YOLOv8 simulation mode active.")

    def detect(self, frame) -> List[Tuple[List[float], float, int]]:
        """
        Runs object detection on an input image frame.
        Filter classes to ensure only 'person' (Class ID 0) is returned.
        Returns:
            List of track-ready detections: [(bbox, confidence, class_id)]
            where bbox is [x1, y1, x2, y2]
        """
        if self.is_simulation:
            return self._simulate_detections(frame)
            
        try:
            # Class ID 0 matches standard person index in COCO models
            results = self.model(
                frame, 
                classes=[0], 
                conf=self.conf_threshold, 
                verbose=False
            )[0]
            
            detections = []
            for box in results.boxes:
                # Extract coordinates
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                
                detections.append(([x1, y1, x2, y2], conf, cls_id))
                
            return detections
        except Exception as e:
            logger.error(f"YOLO detection inference failed: {e}. Falling back to simulation.")
            return self._simulate_detections(frame)

    def _simulate_detections(self, frame) -> List[Tuple[List[float], float, int]]:
        """
        Simulates mock person coordinates to keep down-stream event trackers running in dry runs.
        """
        import random
        # Default viewport dimensions
        h, w = 480, 640
        if frame is not None and hasattr(frame, "shape"):
            h, w = frame.shape[:2]
            
        detections = []
        
        # Seed pseudo-random movement paths relative to time
        # Return 1 to 2 shopper detections moving downward and across the screen
        t = time.time()
        
        # Path 1: Entering store and walking to makeup aisle, then checkout
        # entrance is at y = 380-470, x = 10-630
        x_pos_1 = int(150 + (t % 150) * 2)
        y_pos_1 = int(420 - (t % 100) * 3) # Starts near entrance and moves up
        if 0 < x_pos_1 < w and 0 < y_pos_1 < h:
            detections.append(([x_pos_1 - 40, y_pos_1 - 100, x_pos_1 + 40, y_pos_1 + 100], 0.92, 0))
            
        # Path 2: Person idling in skincare zone
        # skincare zone is x = 320-620, y = 10-180
        x_pos_2 = int(450 + math_sin_variation(t))
        y_pos_2 = int(90 + math_cos_variation(t))
        detections.append(([x_pos_2 - 35, y_pos_2 - 90, x_pos_2 + 35, y_pos_2 + 90], 0.88, 0))
        
        return detections

def math_sin_variation(t: float) -> float:
    import math
    return math.sin(t * 0.5) * 15.0

def math_cos_variation(t: float) -> float:
    import math
    return math.cos(t * 0.3) * 10.0
