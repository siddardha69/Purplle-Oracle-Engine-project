import time
import math
import uuid
import httpx
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from loguru import logger
from pipeline.config import pipeline_settings
from configs.settings import settings

class OcclusionIntelligenceEngine:
    """
    Stateful surveillance co-processor calculating shopper visibility scores,
    detecting rapid visibility collapses, estimating blind spot risks,
    and flagging unexplained shopper disappearances.
    """
    def __init__(self, store_id: str = None):
        self.store_id = store_id or pipeline_settings.STORE_ID
        
        # Track parameters histories
        self.visibility_history: Dict[str, List[float]] = {}
        self.bbox_area_history: Dict[str, List[float]] = {}
        self.detected_frames: Dict[str, int] = {}
        self.total_frames: Dict[str, int] = {}
        
        # Keep track of triggered flags to prevent alert storms
        self.collapse_triggered: Dict[str, bool] = {}
        self.loss_triggered: Dict[str, bool] = {}
        
        # Active anomalies log cache for real-time visualization overlays
        self.active_alerts: Dict[str, dict] = {}
        
        # Proximity markers for entry/exit gate lines
        self.line_start = pipeline_settings.ENTRY_EXIT_LINE[0]
        self.line_end = pipeline_settings.ENTRY_EXIT_LINE[1]

    def _post_anomaly_to_backend(self, anomaly_type: str, severity: str, description: str, metadata: dict):
        """
        Transmits spatial anomalies to the FastAPI REST layer to persist in PostgreSQL/SQLite 
        and broadcast via WebSockets.
        """
        try:
            host = settings.API_HOST if settings.API_HOST != "0.0.0.0" else "localhost"
            url = f"http://{host}:{settings.API_PORT}/api/v1/anomalies"
            
            payload = {
                "store_id": self.store_id,
                "session_id": metadata.get("track_id"),
                "anomaly_type": anomaly_type,
                "severity": severity,
                "description": description,
                "detected_at": datetime.utcnow().isoformat(),
                "metadata": metadata
            }
            # Perform synchronous post to FastAPI in background execution threads safely
            res = httpx.post(url, json=payload, timeout=2.0)
            if res.status_code == 201:
                logger.info(f"Occlusion Engine posted anomaly '{anomaly_type}' successfully.")
            else:
                logger.error(f"Failed to post anomaly: {res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"Failed to post anomaly to backend from OcclusionEngine: {e}")

    def calculate_visibility_score(self, track: Any) -> float:
        """
        Applies a multi-factor confidence model computing real-time visibility scores (0 - 100).
        """
        track_id = track.track_id
        
        # 1. Detection Confidence
        det_conf = getattr(track, 'confidence', 0.8)
        if track.lifecycle == "lost":
            det_conf = 0.0
            
        # 2. Bounding Box Area Stability
        x1, y1, x2, y2 = track.bbox
        area = (x2 - x1) * (y2 - y1)
        prev_areas = self.bbox_area_history.setdefault(track_id, [])
        
        stability = 1.0
        if prev_areas:
            prev_area = prev_areas[-1]
            if prev_area > 0:
                relative_delta = abs(area - prev_area) / prev_area
                stability = 1.0 - min(relative_delta, 1.0)
        prev_areas.append(area)
        if len(prev_areas) > 60:
            prev_areas.pop(0)
            
        # 3. Consecutive Frame Persistence
        persistence_factor = min(len(track.history) / 30.0, 1.0)
        
        # 4. Tracker Confidence
        tracker_conf = 1.0 if track.lifecycle == "active" else 0.0
        
        # 5. Detection Continuity Ratio
        self.total_frames[track_id] = self.total_frames.get(track_id, 0) + 1
        if track.lifecycle == "active":
            self.detected_frames[track_id] = self.detected_frames.get(track_id, 0) + 1
            
        continuity = self.detected_frames.get(track_id, 1) / self.total_frames.get(track_id, 1)
        
        # Weighted blend formula
        score = (
            det_conf * 0.25 + 
            stability * 0.25 + 
            persistence_factor * 0.15 + 
            tracker_conf * 0.20 + 
            continuity * 0.15
        ) * 100.0
        
        return max(0.0, min(100.0, score))

    def update(self, active_tracks: List[Any], current_timestamp: str, active_zones: Dict[str, str]):
        """
        Main update execution loop called on every incoming frame. Updates active track states 
        and flags sudden visibility collapses.
        """
        for track in active_tracks:
            if track.lifecycle != "active":
                continue
                
            track_id = track.track_id
            visibility = self.calculate_visibility_score(track)
            
            scores = self.visibility_history.setdefault(track_id, [])
            scores.append(visibility)
            if len(scores) > 60:
                scores.pop(0)
                
            # Part 2: Visibility Collapse Detection
            # Check for a drop of >= 35 points in the last 5 frames
            if len(scores) >= 5:
                start_score = scores[-5]
                end_score = scores[-1]
                drop = start_score - end_score
                
                if drop >= 35.0 and not self.collapse_triggered.get(track_id, False):
                    self.collapse_triggered[track_id] = True
                    active_zone = active_zones.get(track_id, "unknown_aisle")
                    
                    description = (
                        f"Visibility COLLAPSE for shopper {track_id} from "
                        f"{start_score:.0f}% to {end_score:.0f}% inside {active_zone.replace('_', ' ').title()}."
                    )
                    metadata = {
                        "track_id": track_id,
                        "initial_visibility": round(start_score, 1),
                        "current_visibility": round(end_score, 1),
                        "visibility_change": -round(drop, 1),
                        "last_zone": active_zone,
                        "last_coordinates": track.history[-1] if track.history else [0, 0]
                    }
                    self._post_anomaly_to_backend(
                        anomaly_type="VISIBILITY_COLLAPSE",
                        severity="WARNING",
                        description=description,
                        metadata=metadata
                    )

    def process_lost_tracks(self, lost_tracks: List[Any], current_timestamp: str, active_zones: Dict[str, str]):
        """
        Part 3 - 5: Track Loss Reasoning, Blind Spot Estimation, and Unexplained Disappearances.
        Evaluates tracks transitioning out of the active state.
        """
        for track in lost_tracks:
            track_id = track.track_id
            if track.lifecycle != "lost" and track.lifecycle != "removed":
                continue
                
            if self.loss_triggered.get(track_id, False):
                continue
                
            self.loss_triggered[track_id] = True
            
            # Fetch last known zone
            last_zone = active_zones.get(track_id, "unknown_aisle")
            
            # Calculate coordinates details
            last_coords = track.history[-1] if track.history else [0, 0]
            cx, cy = last_coords
            
            # Get visibility history parameters
            scores = self.visibility_history.get(track_id, [50.0])
            visibility_before_loss = scores[-1] if scores else 50.0
            visibility_collapsed = self.collapse_triggered.get(track_id, False)
            
            # Calculate trajectory vector
            dx, dy = 0.0, 0.0
            if len(track.history) >= 3:
                dx = track.history[-1][0] - track.history[-3][0]
                dy = track.history[-1][1] - track.history[-3][1]
                
            # Verify gate exit line crossings
            crossed_exit = (track.crossing_state == "exited")
            
            # Estimate proximity to standard boundary lines/exits
            # Distance from point to line segment
            near_exit = False
            dist_to_gate = self._point_to_line_dist(last_coords, self.line_start, self.line_end)
            if dist_to_gate < 70.0 or cy > 440.0 or cx < 40.0 or cx > 600.0:
                near_exit = True
                
            # Part 5: Blind Spot Risk Model
            risk = "HIGH"
            risk_score = 85.0
            if crossed_exit or (near_exit and not visibility_collapsed):
                risk = "LOW"
                risk_score = 20.0
            elif "checkout" in last_zone or "billing" in last_zone:
                risk = "MEDIUM"
                risk_score = 55.0
            elif near_exit and visibility_collapsed:
                risk = "MEDIUM"
                risk_score = 60.0
                
            # Part 4: Suspicious Disappearance Detection
            # Disappeared inside product counters without crossing gates after living enough
            is_unexplained = (
                not crossed_exit and 
                len(track.history) >= 10 and 
                (risk in ["HIGH", "MEDIUM"])
            )
            
            alert_type = "TRACK_LOST"
            severity = "INFO"
            if is_unexplained:
                if risk == "HIGH":
                    alert_type = "HIGH_RISK_DISAPPEARANCE"
                    severity = "CRITICAL"
                else:
                    alert_type = "UNEXPLAINED_TRACK_LOSS"
                    severity = "WARNING"
            elif visibility_collapsed:
                alert_type = "POSSIBLE_OCCLUSION"
                severity = "WARNING"
                
            # Part 10: Human-Readable Explainability
            zone_desc = last_zone.replace('_', ' ').title()
            explanation = f"{track_id} disappeared from {zone_desc}. "
            if scores:
                explanation += f"Visibility dropped from {visibility_before_loss:.0f}% to 0%. "
            if crossed_exit:
                explanation += "Verified store boundary gate exit. "
            elif near_exit:
                explanation += "Disappeared near screen exit boundaries. "
            else:
                explanation += "No exit crossing event detected. "
            explanation += f"Risk classified {risk}."
            
            metadata = {
                "track_id": track_id,
                "risk_score": risk_score,
                "risk_class": risk,
                "last_zone": last_zone,
                "visibility_before_loss": round(visibility_before_loss, 1),
                "time_missing": round(time.time() - track.last_update_time, 1),
                "reason": explanation,
                "last_coordinates": last_coords,
                "vector": [round(dx, 2), round(dy, 2)]
            }
            
            # Post anomaly to backend database
            self._post_anomaly_to_backend(
                anomaly_type=alert_type,
                severity=severity,
                description=explanation,
                metadata=metadata
            )
            
            # Cache active alert in Occlusion Engine for Visualizer draw overlays
            self.active_alerts[track_id] = {
                "risk_score": risk_score,
                "risk_class": risk,
                "explanation": explanation,
                "last_coords": last_coords,
                "time_lost": time.time()
            }

    def _point_to_line_dist(self, p: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
        """
        Helper calculating exact minimum perpendicular distance from coordinate P to segment AB.
        """
        px, py = p
        ax, ay = a
        bx, by = b
        
        l2 = (bx - ax)**2 + (by - ay)**2
        if l2 == 0:
            return math.sqrt((px - ax)**2 + (py - ay)**2)
            
        t = max(0, min(1, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / l2))
        proj_x = ax + t * (bx - ax)
        proj_y = ay + t * (by - ay)
        
        return math.sqrt((px - proj_x)**2 + (py - proj_y)**2)
