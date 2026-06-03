import cv2
import time
import numpy as np
from typing import List, Dict, Tuple, Any, Optional
from pipeline.config import pipeline_settings
from pipeline.tracker import TrackState
from pipeline.zones import PolygonZone

class Visualizer:
    """
    Renders computer vision annotations, bounding boxes, trajectory trails,
    and polygon layout borders over CCTV frames for audit inspections.
    """
    def __init__(self, zones: Dict[str, PolygonZone] = None):
        self.zones = zones or {}
        
        # Color palettes definitions matching modern aesthetic
        # Format: (B, G, R)
        self.color_neon_purple = (255, 0, 161)
        self.color_emerald = (118, 230, 0)
        self.color_amber = (0, 191, 255)
        self.color_crimson = (68, 23, 255)
        self.color_slate = (120, 120, 120)
        
        # Gate settings
        self.gate_start = tuple(map(int, pipeline_settings.ENTRY_EXIT_LINE[0]))
        self.gate_end = tuple(map(int, pipeline_settings.ENTRY_EXIT_LINE[1]))

    def draw_annotations(self, frame: np.ndarray, tracks: List[TrackState], current_zones: Dict[str, str], dwells: Dict[str, float] = None, occlusion_engine=None) -> np.ndarray:
        """
        Draws active bounding boxes, tracks histories, polygonal zone areas, 
        and Virtual Gate boundary segments directly onto the image buffer.
        """
        # Create a semi-transparent copy for beautiful layout overlays blending
        overlay = frame.copy()
        
        # 1. Render Polygonal Zones
        for zone_id, zone in self.zones.items():
            pts = np.array(zone.coordinates, dtype=np.int32)
            pts = pts.reshape((-1, 1, 2))
            
            # Select color based on zone types
            if "checkout" in zone_id or "billing" in zone_id:
                color = self.color_crimson
            elif "entrance" in zone_id:
                color = self.color_amber
            else:
                color = self.color_neon_purple
                
            # Draw semi-transparent filled polygon
            cv2.fillPoly(overlay, [pts], color)
            
            # Draw solid polygon boundaries
            cv2.polylines(frame, [pts], True, color, 2)
            
            # Draw Zone Label at centroid
            moments = cv2.moments(pts)
            if moments["m00"] != 0:
                cx = int(moments["m10"] / moments["m00"])
                cy = int(moments["m01"] / moments["m00"])
                cv2.putText(
                    frame, 
                    zone_id.upper(), 
                    (cx - 50, cy), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.45, 
                    (255, 255, 255), 
                    1, 
                    cv2.LINE_AA
                )
                
        # Blend overlay (alpha = 0.15) for glassmorphism layout feel
        cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)

        # 2. Render Virtual Entry/Exit Line
        cv2.line(frame, self.gate_start, self.gate_end, self.color_emerald, 3)
        cv2.putText(
            frame, 
            "VIRTUAL INGESTION GATE (ENTRY/EXIT)", 
            (self.gate_start[0], self.gate_start[1] - 10), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.5, 
            self.color_emerald, 
            2, 
            cv2.LINE_AA
        )

        # 3. Render Visitor Bounding Boxes & Trails
        for track in tracks:
            if track.lifecycle != "active":
                continue
                
            x1, y1, x2, y2 = map(int, track.bbox)
            track_id = track.track_id
            conf = track.confidence
            
            # Retrieve active zone info
            active_zone = current_zones.get(track_id, "NO ZONE")
            
            # Retrieve visibility and risk from occlusion engine if provided
            visibility_percent = int(conf * 100)
            is_high_risk = False
            risk_score = 0
            if occlusion_engine:
                visibility_percent = int(occlusion_engine.visibility_history.get(track_id, [conf * 100])[-1])
                # Check if this active track has a collapse or high risk
                if occlusion_engine.collapse_triggered.get(track_id, False):
                    is_high_risk = True
                    risk_score = 75
                
            # Draw bounding box rectangle (RED if high occlusion risk, else EMERALD)
            box_color = (0, 0, 255) if is_high_risk else self.color_emerald
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
            
            # Draw bottom standing ground point indicator
            cx = int((x1 + x2) / 2.0)
            cy = int(y2)
            cv2.circle(frame, (cx, cy), 5, self.color_amber, -1)
            
            # Draw Trajectory trails
            if len(track.history) > 1:
                pts = np.array(track.history, dtype=np.int32)
                cv2.polylines(frame, [pts], False, self.color_amber, 2)

            # Get dwell seconds
            dwell_sec = 0
            if dwells and track_id in dwells:
                dwell_sec = int(dwells[track_id])

            # Draw Premium Multi-Line Glassmorphic Info Card Overlay
            card_lines = [
                f"TRK: {track_id}",
                f"Zone: {active_zone.title()}",
                f"Dwell: {dwell_sec} sec",
                f"Visibility: {visibility_percent}%"
            ]
            if is_high_risk:
                card_lines.append(f"ALERT: OCCLUSION RISK ({risk_score}%)")
            
            # Calculate text layout sizing
            max_w = 0
            total_h = 4
            line_heights = []
            for line in card_lines:
                (w, h), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
                max_w = max(max_w, w)
                line_heights.append(h)
                total_h += h + 4
                
            # Draw elegant background panel above bounding box
            card_y1 = max(10, y1 - total_h - 10)
            card_y2 = y1 - 4
            cv2.rectangle(frame, (x1, card_y1), (x1 + max_w + 14, card_y2), (0, 0, 0), -1)
            cv2.rectangle(frame, (x1, card_y1), (x1 + max_w + 14, card_y2), box_color, 1)
            
            # Render lines
            curr_y = card_y1 + 10
            for idx, line in enumerate(card_lines):
                line_color = (255, 255, 255) if idx == 0 else (200, 200, 255)
                if "ALERT" in line:
                    line_color = (0, 0, 255)
                cv2.putText(
                    frame, 
                    line, 
                    (x1 + 7, curr_y), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.38, 
                    line_color, 
                    1, 
                    cv2.LINE_AA
                )
                curr_y += line_heights[idx] + 4
                
        # 4. Render Active Track Lost Occlusion Warnings
        if occlusion_engine:
            current_time = time.time()
            for track_id, alert in list(occlusion_engine.active_alerts.items()):
                # Render for 8 seconds after disappearances to avoid permanent canvas cluttering
                if current_time - alert["time_lost"] > 8.0:
                    continue
                    
                risk_class = alert["risk_class"]
                if risk_class not in ["HIGH", "MEDIUM"]:
                    continue
                    
                cx, cy = map(int, alert["last_coords"])
                risk_score = alert["risk_score"]
                
                # Draw a dashed-like RED circle or crosshair indicator at the disappearance location
                cv2.circle(frame, (cx, cy), 22, (0, 0, 255), 2)
                cv2.line(frame, (cx - 30, cy), (cx + 30, cy), (0, 0, 255), 2)
                cv2.line(frame, (cx, cy - 30), (cx, cy + 30), (0, 0, 255), 2)
                
                # Draw track lost red info card
                card_x = max(10, cx - 75)
                card_y = max(10, cy - 85)
                cv2.rectangle(frame, (card_x, card_y), (card_x + 150, card_y + 50), (0, 0, 0), -1)
                cv2.rectangle(frame, (card_x, card_y), (card_x + 150, card_y + 50), (0, 0, 255), 1)
                
                cv2.putText(frame, "⚠️ TRACK LOST WARNING", (card_x + 6, card_y + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1, cv2.LINE_AA)
                cv2.putText(frame, f"ID: {track_id}", (card_x + 6, card_y + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.putText(frame, f"RISK: {risk_score}% ({risk_class})", (card_x + 6, card_y + 42), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (200, 200, 255), 1, cv2.LINE_AA)
            
        return frame

    def draw_heatmap_overlay(self, frame: np.ndarray, points: List[Tuple[int, int]]) -> np.ndarray:
        """
        Overlays a thermal-color spatial density heatmap directly onto the camera frames.
        """
        if not points:
            return frame
            
        h, w = frame.shape[:2]
        accum = np.zeros((h, w), dtype=np.float32)
        for x, y in points:
            if 0 <= x < w and 0 <= y < h:
                cv2.circle(accum, (int(x), int(y)), 25, 1.0, -1)
                
        accum = cv2.GaussianBlur(accum, (51, 51), 0)
        cv2.normalize(accum, accum, 0, 255, cv2.NORM_MINMAX)
        accum = accum.astype(np.uint8)
        
        # Colorize using OpenCV's Jet colormap
        heatmap_img = cv2.applyColorMap(accum, cv2.COLORMAP_JET)
        
        # Blend semi-transparently with the source frame
        cv2.addWeighted(heatmap_img, 0.45, frame, 0.55, 0, frame)
        return frame

    def display_frame(self, frame: np.ndarray, window_name: str = "Purplle CCTV Live Stream"):
        """
        Renders frame using high-performance OpenCV graphical windows loops.
        """
        cv2.imshow(window_name, frame)
        # Small wait key to allow UI frames rendering execution
        cv2.waitKey(1)

    def close_all_windows(self):
        cv2.destroyAllWindows()
