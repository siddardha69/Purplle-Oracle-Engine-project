import numpy as np
from typing import List, Dict, Any
from loguru import logger

class CentroidTracker:
    """
    Centroid tracking fallback algorithm.
    Tracks bounding boxes across consecutive frames using Euclidean distance matches.
    """
    def __init__(self, max_disappeared=10):
        self.next_object_id = 1
        self.objects = {}       # id -> centroid coordinates (cx, cy)
        self.disappeared = {}   # id -> frame absence count
        self.max_disappeared = max_disappeared

    def register(self, centroid):
        self.objects[self.next_object_id] = centroid
        self.disappeared[self.next_object_id] = 0
        self.next_object_id += 1

    def deregister(self, object_id):
        del self.objects[object_id]
        del self.disappeared[object_id]

    def update(self, rects: List[List[float]]) -> Dict[int, List[float]]:
        """
        rects: list of bounding boxes [x1, y1, x2, y2]
        Returns: Dict mapping tracker IDs to bounding boxes.
        """
        if len(rects) == 0:
            # Increment disappearance count for all existing objects
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return {}

        # Compute centroids of incoming boxes
        input_centroids = np.zeros((len(rects), 2), dtype="int")
        for (i, (startX, startY, endX, endY)) in enumerate(rects):
            cx = int((startX + endX) / 2.0)
            cy = int((startY + endY) / 2.0)
            input_centroids[i] = (cx, cy)

        # If we aren't tracking any objects, register all inputs
        if len(self.objects) == 0:
            for i in range(len(input_centroids)):
                self.register(input_centroids[i])
        else:
            object_ids = list(self.objects.keys())
            object_centroids = list(self.objects.values())

            # Compute Euclidean distances between existing and incoming centroids
            D = np.linalg.norm(np.array(object_centroids)[:, np.newaxis] - input_centroids, axis=2)

            # Find matching centroids (row minimums)
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            used_rows = set()
            used_cols = set()

            for (row, col) in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue

                object_id = object_ids[row]
                self.objects[object_id] = input_centroids[col]
                self.disappeared[object_id] = 0

                used_rows.add(row)
                used_cols.add(col)

            # Deregister lost objects or register new inputs
            unused_rows = set(range(0, D.shape[0])).difference(used_rows)
            unused_cols = set(range(0, D.shape[1])).difference(used_cols)

            for row in unused_rows:
                object_id = object_ids[row]
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)

            for col in unused_cols:
                self.register(input_centroids[col])

        # Return active boxes mapped to their assigned tracker ID
        results = {}
        for object_id, centroid in self.objects.items():
            # Find the rect closest to this tracked centroid
            min_dist = float("inf")
            best_rect = None
            for rect in rects:
                rcx = int((rect[0] + rect[2]) / 2.0)
                rcy = int((rect[1] + rect[3]) / 2.0)
                dist = np.linalg.norm(np.array([rcx, rcy]) - centroid)
                if dist < min_dist:
                    min_dist = dist
                    best_rect = rect
            if best_rect:
                results[object_id] = best_rect
                
        return results

class ByteTrackTracker:
    """
    Multi-Object tracking wrapper.
    Utilizes localized CentroidTracker for seamless CPU/offline bootstrapping, 
    designed to easily transition to ByteTrack algorithms.
    """
    def __init__(self):
        logger.info("Initializing Store Intelligence Multi-Object Tracker (Centroid/ByteTrack)...")
        self.tracker = CentroidTracker(max_disappeared=15)

    def track(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Receives raw bounding boxes and returns persistent tracking IDs.
        Returns: List containing tracks:
                 [{"track_id": 1, "bbox": [x1, y1, x2, y2], "confidence": 0.95}]
        """
        rects = [det["bbox"] for det in detections]
        tracked_objects = self.tracker.update(rects)
        
        tracks = []
        for obj_id, bbox in tracked_objects.items():
            # Match confidence score from original detections
            conf = 0.9
            for det in detections:
                # Find matching rect
                if np.allclose(det["bbox"], bbox, atol=10.0):
                    conf = det["confidence"]
                    break
                    
            tracks.append({
                "track_id": f"TRK-{obj_id:04d}",
                "bbox": bbox,
                "confidence": conf
            })
            
        return tracks
