import time
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from loguru import logger
from pipeline.config import pipeline_settings

class TrackState:
    """
    Holds persistent profile telemetry for individual shopper traces.
    """
    def __init__(self, track_id: str, initial_bbox: List[float], confidence: float):
        self.track_id = track_id
        self.bbox = initial_bbox
        self.confidence = confidence
        
        # Trajectory history: List of bottom-center (cx, cy) coords
        self.history: List[Tuple[float, float]] = []
        self._update_history(initial_bbox)
        
        # Lifecycle states: active, lost, removed
        self.lifecycle: str = "active"
        
        # Entry/Exit cross trackers to debounce duplicates
        # States: None (not crossed), "entered", "exited"
        self.crossing_state: Optional[str] = None
        self.last_update_time = time.time()

    def update(self, bbox: List[float], confidence: float):
        self.bbox = bbox
        self.confidence = confidence
        self._update_history(bbox)
        self.lifecycle = "active"
        self.last_update_time = time.time()

    def mark_lost(self):
        self.lifecycle = "lost"

    def _update_history(self, bbox: List[float]):
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = y2  # Standing location floor coordinates
        self.history.append((cx, cy))
        
        # Cap trajectory history at last 150 frames to avoid memory leaks
        if len(self.history) > 150:
            self.history.pop(0)

class MultiObjectTracker:
    """
    High-performance shopper centroids tracking engine.
    Computes trajectory vectors, maintains ID indices, and evaluates virtual gates crossings.
    """
    def __init__(self):
        self.tracks: Dict[str, TrackState] = {}
        self.next_id_val = 1
        
        # Virtual Gate points from configuration settings
        self.line_start = pipeline_settings.ENTRY_EXIT_LINE[0]
        self.line_end = pipeline_settings.ENTRY_EXIT_LINE[1]
        
        # Debounce registry to verify crossing operations
        # Maps track_id to set of events triggered to prevent repeat execution
        self.triggered_events: Dict[str, set] = {}

    def update(self, detections: List[Tuple[List[float], float, int]]) -> List[TrackState]:
        """
        Receives raw bounding boxes, matches them to existing tracks using centroid distance tracking, 
        updates trajectories, and handles track births and terminations.
        """
        rects = [det[0] for det in detections]
        confidences = [det[1] for det in detections]
        
        active_tracks = []
        
        # Handle zero-detection frames by updating lost metrics
        if len(rects) == 0:
            for track in self.tracks.values():
                if track.lifecycle == "active":
                    track.mark_lost()
            return list(self.tracks.values())

        # Extract centroids of incoming detections
        input_centroids = np.zeros((len(rects), 2))
        for idx, bbox in enumerate(rects):
            x1, y1, x2, y2 = bbox
            cx = (x1 + x2) / 2.0
            cy = y2
            input_centroids[idx] = (cx, cy)

        # Get list of currently active tracks
        current_tracks = [t for t in self.tracks.values() if t.lifecycle == "active"]
        
        if len(current_tracks) == 0:
            # Register all incoming detections as brand new tracks
            for idx in range(len(input_centroids)):
                self._register_track(rects[idx], confidences[idx])
        else:
            # Extract historical centroids
            track_centroids = np.zeros((len(current_tracks), 2))
            for idx, track in enumerate(current_tracks):
                track_centroids[idx] = track.history[-1]

            # Compute Euclidean distances between existing and incoming centroids
            D = np.linalg.norm(track_centroids[:, np.newaxis] - input_centroids, axis=2)

            # Minimum distance matches
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            used_rows = set()
            used_cols = set()

            for (row, col) in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue
                
                # Filter out extremely far matches to prevent ghost trackers jumps
                if D[row, col] > 180.0:
                    continue

                track = current_tracks[row]
                track.update(rects[col], confidences[col])
                
                used_rows.add(row)
                used_cols.add(col)

            # Mark missing tracks as lost
            unused_rows = set(range(0, D.shape[0])).difference(used_rows)
            for row in unused_rows:
                current_tracks[row].mark_lost()

            # Register unmatched detections as new tracks
            unused_cols = set(range(0, D.shape[1])).difference(used_cols)
            for col in unused_cols:
                self._register_track(rects[col], confidences[col])

        # Clean up stale track references that remained lost for > 60 frames
        current_time = time.time()
        for track_id, track in list(self.tracks.items()):
            if track.lifecycle == "lost" and (current_time - track.last_update_time) > 15.0:
                track.lifecycle = "removed"
                
        return list(self.tracks.values())

    def _register_track(self, bbox: List[float], confidence: float):
        track_id = f"TRK-{self.next_id_val:04d}"
        self.tracks[track_id] = TrackState(track_id, bbox, confidence)
        self.triggered_events[track_id] = set()
        self.next_id_val += 1
        logger.info(f"Registered new shopper track: {track_id}")

    def check_line_crossing(self, track: TrackState) -> Optional[str]:
        """
        Evaluates track coordinates history segment intersections against virtual entry/exit gate lines.
        Returns:
            "ENTRY" if track crossed inwards,
            "EXIT" if track crossed outwards,
            None if no crossing occurred this step or already debounced.
        """
        # Need at least two frames of historical data to evaluate vectors
        if len(track.history) < 2:
            return None
            
        p1 = track.history[-2] # Coordinates before
        p2 = track.history[-1] # Coordinates current
        
        # Check segment intersection
        intersected = self._segments_intersect(p1, p2, self.line_start, self.line_end)
        
        if intersected:
            # Determine crossing direction
            # Vector AB (shopper trajectory)
            ab_vector = np.array([p2[0] - p1[0], p2[1] - p1[1]])
            
            # Virtual Gate vector
            gate_vector = np.array([self.line_end[0] - self.line_start[0], self.line_end[1] - self.line_start[1]])
            
            # Normal vector to gate pointing inwards
            # gate_vector = (dx, dy) -> normal_vector = (-dy, dx)
            normal_vector = np.array([-gate_vector[1], gate_vector[0]])
            normal_vector = normal_vector / np.linalg.norm(normal_vector) # Normalize
            
            # Evaluate projection dot product
            dot_product = np.dot(ab_vector, normal_vector)
            
            # Check direction based on dot product threshold
            if dot_product > 0:
                # Crossed in positive normal vector direction (representing ENTRY)
                if "ENTRY" not in self.triggered_events[track.track_id]:
                    self.triggered_events[track.track_id].add("ENTRY")
                    track.crossing_state = "entered"
                    logger.info(f"Track {track.track_id} triggered virtual line intersection: ENTRY")
                    return "ENTRY"
            else:
                # Crossed in negative direction (representing EXIT)
                if "EXIT" not in self.triggered_events[track.track_id]:
                    self.triggered_events[track.track_id].add("EXIT")
                    track.crossing_state = "exited"
                    logger.info(f"Track {track.track_id} triggered virtual line intersection: EXIT")
                    return "EXIT"
                    
        return None

    def _ccw(self, A, B, C) -> bool:
        """
        Helper returning orientation (Counter-Clockwise) check for segment intersection calculations.
        """
        return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])

    def _segments_intersect(self, A, B, C, D) -> bool:
        """
        Evaluates whether segment AB intersects CD.
        """
        return self._ccw(A,C,D) != self._ccw(B,C,D) and self._ccw(A,B,C) != self._ccw(A,B,D)
