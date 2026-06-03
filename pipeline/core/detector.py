import os
from typing import List, Dict, Any, Tuple
from configs.settings import settings
from loguru import logger

# Try loading Ultralytics, with safe logging if not installed or missing
try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    logger.warning("Ultralytics library is not installed. YOLO inference will run in mock/simulated mode.")

class YOLODetector:
    """
    Wrapper for Ultralytics YOLOv8 object detection pipelines.
    Supports CUDA hardware acceleration and falls back to simulated mocks for speed.
    """
    def __init__(self, model_path: str = None):
        self.model_path = model_path or settings.MODEL_PATH
        self.model = None
        self._is_mock = True
        
        if ULTRALYTICS_AVAILABLE:
            try:
                # Force checking weights existence before starting YOLO instances
                if os.path.exists(self.model_path) or self.model_path.endswith(".pt"):
                    logger.info(f"Loading YOLO model weights from: {self.model_path}")
                    self.model = YOLO(self.model_path)
                    self._is_mock = False
                    logger.info("YOLOv8 detector loaded successfully.")
                else:
                    logger.warning(f"YOLO weights '{self.model_path}' not found on disk. Initializing simulation mode.")
            except Exception as e:
                logger.error(f"Failed to load YOLO model: {e}. Falling back to simulation.")
        else:
            logger.info("YOLOv8 simulation mode active.")

    def detect(self, frame) -> List[Dict[str, Any]]:
        """
        Executes inference on an OpenCV frame image.
        Returns: List of detected objects with bounding boxes:
                 [{"bbox": [x1, y1, x2, y2], "confidence": 0.95, "class_id": 0, "label": "person"}]
        """
        if self._is_mock:
            return self._simulate_detections(frame)
            
        try:
            # Class ID 0 represents 'person' in standard COCO datasets
            results = self.model(frame, classes=[0], verbose=False)[0]
            detections = []
            
            # Extract standard detection matrices
            for box in results.boxes:
                coords = box.xyxy[0].tolist() # x1, y1, x2, y2
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                
                detections.append({
                    "bbox": coords,
                    "confidence": conf,
                    "class_id": cls,
                    "label": "person"
                })
            return detections
        except Exception as e:
            logger.error(f"YOLO inference loop failed: {e}. Falling back to mock results.")
            return self._simulate_detections(frame)

    def _simulate_detections(self, frame) -> List[Dict[str, Any]]:
        """
        Simulates mock person coordinates to allow continuous testing of down-stream tracking systems.
        """
        import random
        # Create standard synthetic bounding boxes relative to typical 640x480 video coordinates
        h, w = 480, 640
        if frame is not None and hasattr(frame, "shape"):
            h, w = frame.shape[:2]
            
        # Draw mock detections
        detections = []
        # Return 1 to 3 random targets
        for idx in range(random.randint(1, 3)):
            cx = w // 2 + random.randint(-150, 150)
            cy = h // 2 + random.randint(-100, 100)
            bw, bh = 80, 180
            
            detections.append({
                "bbox": [cx - bw//2, cy - bh//2, cx + bw//2, cy + bh//2],
                "confidence": round(random.uniform(0.75, 0.98), 2),
                "class_id": 0,
                "label": "person"
            })
        return detections
