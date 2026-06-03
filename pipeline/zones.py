import json
import os
import time
from typing import Dict, Any, List, Tuple, Optional
from shapely.geometry import Point, Polygon
from loguru import logger
from pipeline.config import pipeline_settings

class PolygonZone:
    """
    Polygonal spatial segment mapping floor locations.
    """
    def __init__(self, zone_id: str, coordinates: List[List[float]]):
        self.zone_id = zone_id
        self.coordinates = coordinates
        if len(coordinates) < 3:
            raise ValueError(f"Spatial polygon zone requires at least 3 vertex pairs. Zone: {zone_id}")
            
        # Convert lists to tuples list
        vertices = [tuple(c) for c in coordinates]
        self.polygon = Polygon(vertices)

    def contains_point(self, x: float, y: float) -> bool:
        """
        Runs Shapely point-in-polygon calculations.
        """
        p = Point(x, y)
        return self.polygon.contains(p)

class ZoneManager:
    """
    Orchestrates physical zone intersections, parsing configs and managing transition streams.
    """
    def __init__(self, layout_path: str = None):
        self.layout_path = layout_path or pipeline_settings.LAYOUT_PATH
        self.zones: Dict[str, PolygonZone] = {}
        
        # Track persistent current zones per track ID: {track_id: zone_name}
        self.active_visitor_zones: Dict[str, str] = {}
        
        self._load_layout()

    def _load_layout(self):
        """
        Parses polygonal zones from store_layout.json.
        """
        if os.path.exists(self.layout_path):
            try:
                with open(self.layout_path, "r") as f:
                    layout = json.load(f)
                
                zones_data = layout.get("zones", {})
                for zone_id, vertices in zones_data.items():
                    self.zones[zone_id] = PolygonZone(zone_id, vertices)
                    
                logger.info(f"Successfully configured {len(self.zones)} polygon zones from {self.layout_path}.")
                return
            except Exception as e:
                logger.error(f"Failed to parse store layout coordinates at {self.layout_path}: {e}")
                
        # Enforce default fallback zones if layout configuration is not present on disk
        logger.warning("Deploying local mock shopping layout dimensions.")
        fallback_zones = {
            "store_entrance": [[10, 380], [630, 380], [630, 470], [10, 470]],
            "makeup_zone": [[10, 10], [300, 10], [300, 180], [10, 180]],
            "skincare_zone": [[320, 10], [620, 10], [620, 180], [320, 180]],
            "fragrance_counter": [[10, 200], [300, 200], [300, 350], [10, 350]],
            "checkout_zone": [[320, 200], [620, 200], [620, 350], [320, 350]]
        }
        for zone_id, vertices in fallback_zones.items():
            self.zones[zone_id] = PolygonZone(zone_id, vertices)

    def evaluate_visitor_position(self, track_id: str, cx: float, cy: float) -> List[Tuple[str, str]]:
        """
        Evaluates a shopper bottom-center coordinates, identifies zone intersections,
        and generates state transition events (ZONE_ENTER, ZONE_EXIT).
        Returns:
            List of tuples detailing transition events: [("ZONE_EXIT", zone_id), ("ZONE_ENTER", zone_id)]
        """
        intersected_zone = None
        
        # Check point intersections across all zones
        for zone_id, zone in self.zones.items():
            if zone.contains_point(cx, cy):
                intersected_zone = zone_id
                break
                
        previous_zone = self.active_visitor_zones.get(track_id)
        events = []
        
        # Determine transition sequences
        if previous_zone != intersected_zone:
            if previous_zone is not None:
                # Visitor exited previous zone
                events.append(("ZONE_EXIT", previous_zone))
                logger.debug(f"Shopper {track_id} exited zone: {previous_zone}")
                
            if intersected_zone is not None:
                # Visitor entered a new zone
                events.append(("ZONE_ENTER", intersected_zone))
                logger.debug(f"Shopper {track_id} entered zone: {intersected_zone}")
                
            # Update cache registry
            if intersected_zone is not None:
                self.active_visitor_zones[track_id] = intersected_zone
            else:
                self.active_visitor_zones.pop(track_id, None)
                
        return events

    def force_visitor_exit(self, track_id: str) -> List[Tuple[str, str]]:
        """
        Forcibly exits a customer track out of their active zone.
        Useful when a tracking trace drops out of the camera view.
        """
        events = []
        previous_zone = self.active_visitor_zones.pop(track_id, None)
        if previous_zone:
            events.append(("ZONE_EXIT", previous_zone))
            logger.debug(f"Shopper {track_id} dropped tracking trace. Firing forced exit: {previous_zone}")
        return events


class DwellTracker:
    """
    Tracks customer stay timings within store layout polygon zones.
    Fires intermediate ZONE_DWELL events every 30 seconds of continuous loitering.
    """
    def __init__(self):
        # Maps (track_id, zone_id) -> zone_entry_unix_timestamp
        self.entry_times: Dict[Tuple[str, str], float] = {}
        # Maps (track_id, zone_id) -> last_dwell_event_unix_timestamp
        self.last_dwell_events: Dict[Tuple[str, str], float] = {}
        
        self.dwell_interval_s = pipeline_settings.DWELL_INTERVAL_MS / 1000.0 # 30 seconds

    def process_zone_entry(self, track_id: str, zone_id: str):
        """
        Records the exact time the customer enters a zone.
        """
        curr_time = time.time()
        self.entry_times[(track_id, zone_id)] = curr_time
        self.last_dwell_events[(track_id, zone_id)] = curr_time

    def process_zone_exit(self, track_id: str, zone_id: str) -> float:
        """
        Clears timing records on zone exit and returns total dwell duration in milliseconds.
        """
        entry_time = self.entry_times.pop((track_id, zone_id), None)
        self.last_dwell_events.pop((track_id, zone_id), None)
        
        if entry_time:
            duration_s = time.time() - entry_time
            return duration_s * 1000.0 # Convert to milliseconds
        return 0.0

    def check_for_dwell_events(self, track_id: str, zone_id: str) -> Optional[float]:
        """
        Evaluates active loitering. If continuous duration exceeds the 30s interval boundaries,
        returns current total dwell elapsed in milliseconds to trigger ZONE_DWELL event.
        """
        entry_key = (track_id, zone_id)
        entry_time = self.entry_times.get(entry_key)
        last_dwell = self.last_dwell_events.get(entry_key)
        
        if not entry_time or not last_dwell:
            return None
            
        curr_time = time.time()
        
        # Check if 30s has elapsed since last dwell push
        if (curr_time - last_dwell) >= self.dwell_interval_s:
            # Update last dwell event tracker
            self.last_dwell_events[entry_key] = curr_time
            total_dwell_ms = (curr_time - entry_time) * 1000.0
            logger.info(f"Shopper {track_id} loitering in '{zone_id}' for {total_dwell_ms/1000.0:.1f}s. Triggering DWELL.")
            return total_dwell_ms
            
        return None

    def clear_track_records(self, track_id: str):
        """
        Sweeps clean all lingering registers of dropped tracks.
        """
        keys_to_clear = [k for k in self.entry_times.keys() if k[0] == track_id]
        for key in keys_to_clear:
            self.entry_times.pop(key, None)
            self.last_dwell_events.pop(key, None)
