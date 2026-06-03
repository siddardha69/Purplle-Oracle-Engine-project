import time
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from loguru import logger
from pipeline.config import pipeline_settings

class ReIDProfile:
    """
    Profile snapshot of a lost shopper trace to facilitate Re-ID matching.
    """
    def __init__(self, track_id: str, shopper_id: str, last_centroid: Tuple[float, float], last_bbox: List[float]):
        self.track_id = track_id
        self.shopper_id = shopper_id
        self.last_centroid = last_centroid
        
        # Calculate Bbox Aspect Ratio (Width / Height) to evaluate shopper shape profiles
        x1, y1, x2, y2 = last_bbox
        w = x2 - x1
        h = y2 - y1
        self.aspect_ratio = w / (h if h > 0 else 1.0)
        
        self.disappeared_time = time.time()

class ReEntryManager:
    """
    Tracks disappearing traces and runs multi-criteria matching sweeps 
    when new tracks emerge to identify returning shoppers.
    """
    def __init__(self):
        # Maps active track_ids to persistent global shopper_ids
        self.track_to_shopper: Dict[str, str] = {}
        
        # Historical registry of lost shopper profiles
        self.history_pool: List[ReIDProfile] = []
        
        # Load parameters
        self.time_window = pipeline_settings.REID_TIME_WINDOW_SECONDS
        self.max_distance = pipeline_settings.REID_MAX_DISTANCE_PX
        self.aspect_ratio_tolerance = pipeline_settings.REID_ASPECT_RATIO_TOLERANCE

    def get_shopper_id(self, track_id: str) -> str:
        """
        Returns the persistent shopper ID mapped to a camera track ID.
        """
        # If not mapped, map it to itself initially
        if track_id not in self.track_to_shopper:
            self.track_to_shopper[track_id] = track_id
        return self.track_to_shopper[track_id]

    def register_lost_track(self, track_id: str, last_centroid: Tuple[float, float], last_bbox: List[float]):
        """
        Takes snapshot of lost tracking traces and stores them in the comparison pool.
        """
        shopper_id = self.get_shopper_id(track_id)
        profile = ReIDProfile(track_id, shopper_id, last_centroid, last_bbox)
        self.history_pool.append(profile)
        logger.info(f"Buffered lost track {track_id} (Shopper: {shopper_id}) to ReID pool.")
        
        # Periodically purge history pool to keep search space small
        self._prune_history_pool()

    def check_for_reentry(self, new_track_id: str, new_centroid: Tuple[float, float], new_bbox: List[float]) -> Optional[str]:
        """
        Scans lost profile histories. Reconnects returning shoppers and returns their persistent shopper ID.
        Returns:
            Persistent shopper ID if matched, triggering a REENTRY event,
            None if new shopper.
        """
        self._prune_history_pool()
        
        if not self.history_pool:
            return None

        # Compute aspect ratio of new detection
        nx1, ny1, nx2, ny2 = new_bbox
        nw = nx2 - nx1
        nh = ny2 - ny1
        new_aspect_ratio = nw / (nh if nh > 0 else 1.0)
        
        best_match: Optional[ReIDProfile] = None
        best_distance = float("inf")
        
        curr_time = time.time()
        
        # Scan profiles pool
        for profile in self.history_pool:
            # 1. Temporal bounds check (5 minutes max)
            time_diff = curr_time - profile.disappeared_time
            if time_diff > self.time_window:
                continue
                
            # 2. Spatial distance check (max px distance)
            dist = np.linalg.norm(np.array(new_centroid) - np.array(profile.last_centroid))
            if dist > self.max_distance:
                continue
                
            # 3. Shape aspect ratio validation
            ratio_diff = abs(new_aspect_ratio - profile.aspect_ratio) / profile.aspect_ratio
            if ratio_diff > self.aspect_ratio_tolerance:
                continue
                
            # Keep match with closest spatial distance
            if dist < best_distance:
                best_distance = dist
                best_match = profile

        if best_match:
            # Match registered successfully!
            matched_shopper_id = best_match.shopper_id
            
            # Map new track_id to historical shopper_id
            self.track_to_shopper[new_track_id] = matched_shopper_id
            
            # Remove profile from history pool to prevent double matching
            self.history_pool.remove(best_match)
            
            logger.info(
                f"ReID Match Found! Track {new_track_id} matched to historical trace {best_match.track_id}. "
                f"Shopper ID unified to {matched_shopper_id}."
            )
            return matched_shopper_id
            
        return None

    def _prune_history_pool(self):
        """
        Removes profiles that have been disappeared for longer than the search time window.
        """
        curr_time = time.time()
        self.history_pool = [
            p for p in self.history_pool 
            if (curr_time - p.disappeared_time) <= self.time_window
        ]
