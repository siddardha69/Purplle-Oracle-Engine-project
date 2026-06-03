import threading
import time
import cv2
import httpx
from typing import Dict, Any, List, Tuple
from loguru import logger
from pipeline.main import RetailVisionPipeline
from configs.settings import settings
from datetime import datetime

class BackgroundPipelineStreamer:
    """
    Manages background execution of the RetailVisionPipeline for a store
    and exposes the latest frames as JPEG buffers and live telemetry.
    """
    def __init__(self, store_id: str):
        self.store_id = store_id
        self.pipeline_engine = None
        self.frame_iterator = None
        self.latest_standard_frame = None
        self.latest_heatmap_frame = None
        self.is_running = False
        self.play = True
        self.heatmap_points = []
        self.thread = None
        
    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            logger.info(f"Background pipeline streamer started for store: {self.store_id}")
            
    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info(f"Background pipeline streamer stopped for store: {self.store_id}")

    def _post_event_to_api(self, event_data: dict):
        try:
            # Map telemetry event to backend Pydantic VisitorEventCreate schema
            raw_type = event_data.get("event_type", "ZONE_ENTER")
            mapped_type = "ENTER"
            if "EXIT" in raw_type:
                mapped_type = "EXIT"
            elif "DWELL" in raw_type:
                mapped_type = "DWELL"
                
            zone = event_data.get("zone_id") or "virtual_gate"
            session_id = event_data.get("visitor_id", "TRK-UNKNOWN")
            timestamp = event_data.get("timestamp") or datetime.utcnow().isoformat()
            duration_sec = float(event_data.get("dwell_ms", 0)) / 1000.0
            camera_id = event_data.get("camera_id") or "CAM-MAIN-01"
            
            api_payload = {
                "zone_name": zone,
                "event_type": mapped_type,
                "event_timestamp": timestamp,
                "duration": duration_sec,
                "session_id": session_id,
                "camera_id": camera_id,
                "metadata": {
                    "confidence": event_data.get("confidence", 1.0),
                    "is_staff": event_data.get("is_staff", False),
                    "bbox": event_data.get("metadata", {}).get("bbox", []),
                    "store_id": self.store_id
                }
            }
            
            host = settings.API_HOST if settings.API_HOST != "0.0.0.0" else "localhost"
            url = f"http://{host}:{settings.API_PORT}/api/v1/events"
            httpx.post(url, json=api_payload, timeout=1.0)
        except Exception as e:
            logger.error(f"Failed to post live event to API from bg thread: {e}")

    def _run_loop(self):
        try:
            self.pipeline_engine = RetailVisionPipeline()
            # Force store ID to match this streamer
            self.pipeline_engine.store_id = self.store_id
            self.frame_iterator = self.pipeline_engine.loader.iter_frames()
            # Instantiate Occlusion intelligence co-processor
            from pipeline.occlusion_engine import OcclusionIntelligenceEngine
            self.occlusion_engine = OcclusionIntelligenceEngine(self.store_id)
        except Exception as init_err:
            logger.error(f"Failed to initialize bg pipeline context for {self.store_id}: {init_err}")
            self.is_running = False
            return

        frame_counter = 0
        while self.is_running:
            if not self.play:
                # If paused, sleep and continue
                time.sleep(0.1)
                continue
                
            frame_counter += 1
            try:
                frame_idx, timestamp, frame = next(self.frame_iterator)
            except StopIteration:
                # Loop video
                self.frame_iterator = self.pipeline_engine.loader.iter_frames()
                try:
                    frame_idx, timestamp, frame = next(self.frame_iterator)
                except Exception as loop_err:
                    logger.error(f"Error looping video frame generator: {loop_err}")
                    time.sleep(1.0)
                    continue
            except Exception as frame_err:
                logger.error(f"Error fetching next video frame: {frame_err}")
                time.sleep(0.5)
                continue

            raw_frame = frame.copy()
            
            # 1. Object Detections (YOLO)
            detections = self.pipeline_engine.detector.detect(raw_frame)
            
            # Normalize coordinates
            frame_h, frame_w = raw_frame.shape[:2]
            scale_x = 640.0 / frame_w
            scale_y = 480.0 / frame_h
            
            normalized_detections = []
            for bbox, conf, cls_id in detections:
                x1, y1, x2, y2 = bbox
                normalized_detections.append(([x1 * scale_x, y1 * scale_y, x2 * scale_x, y2 * scale_y], conf, cls_id))
                
            # 2. Tracks Detections
            tracks = self.pipeline_engine.tracker.update(normalized_detections)
            
            active_zones_mapping = {}
            dwells = {}
            
            # Update Active Zones Map first to ensure it's fully populated for all active tracks
            for track in tracks:
                if track.lifecycle == "active":
                    x1, y1, x2, y2 = track.bbox
                    cx = (x1 + x2) / 2.0
                    cy = y2
                    active_zone = self.pipeline_engine.zone_manager.active_visitor_zones.get(track.track_id)
                    if active_zone:
                        active_zones_mapping[track.track_id] = active_zone

            # Update Occlusion Engine Visibility Models in real-time
            self.occlusion_engine.update(tracks, timestamp, active_zones_mapping)
            
            for track in tracks:
                if track.lifecycle != "active":
                    continue
                track_id = track.track_id
                visitor_id, is_reentry = self.pipeline_engine.get_unified_shopper_id(track, timestamp)
                
                if is_reentry:
                    reentry_event = {
                        "store_id": self.pipeline_engine.store_id,
                        "camera_id": self.pipeline_engine.camera_id,
                        "visitor_id": visitor_id,
                        "event_type": "REENTRY",
                        "timestamp": timestamp,
                        "confidence": float(track.confidence),
                        "metadata": {"bbox": track.bbox, "reassigned_track": track_id}
                    }
                    self.pipeline_engine.emitter.emit(reentry_event)
                    self._post_event_to_api(reentry_event)
                    
                crossing_type = self.pipeline_engine.tracker.check_line_crossing(track)
                if crossing_type == "ENTRY":
                    entry_event = {
                        "store_id": self.pipeline_engine.store_id,
                        "camera_id": self.pipeline_engine.camera_id,
                        "visitor_id": visitor_id,
                        "event_type": "ENTRY",
                        "timestamp": timestamp,
                        "confidence": float(track.confidence),
                        "metadata": {"bbox": track.bbox}
                    }
                    self.pipeline_engine.emitter.emit(entry_event)
                    self._post_event_to_api(entry_event)
                elif crossing_type == "EXIT":
                    exit_event = {
                        "store_id": self.pipeline_engine.store_id,
                        "camera_id": self.pipeline_engine.camera_id,
                        "visitor_id": visitor_id,
                        "event_type": "EXIT",
                        "timestamp": timestamp,
                        "confidence": float(track.confidence),
                        "metadata": {"bbox": track.bbox}
                    }
                    self.pipeline_engine.emitter.emit(exit_event)
                    self._post_event_to_api(exit_event)
                    
                x1, y1, x2, y2 = track.bbox
                cx = (x1 + x2) / 2.0
                cy = y2
                
                zone_transitions = self.pipeline_engine.zone_manager.evaluate_visitor_position(track_id, cx, cy)
                active_zone = self.pipeline_engine.zone_manager.active_visitor_zones.get(track_id)
                if active_zone:
                    entry_time = self.pipeline_engine.dwell_tracker.entry_times.get((track_id, active_zone))
                    if entry_time:
                        dwells[track_id] = int(time.time() - entry_time)
                    self.heatmap_points.append((int(cx), int(cy)))
                    
                is_staff = self.pipeline_engine.check_staff_classification(track, active_zone)
                for transition_type, zone_id in zone_transitions:
                    if transition_type == "ZONE_ENTER":
                        self.pipeline_engine.dwell_tracker.process_zone_entry(track_id, zone_id)
                        enter_event = {
                            "store_id": self.pipeline_engine.store_id,
                            "camera_id": self.pipeline_engine.camera_id,
                            "visitor_id": visitor_id,
                            "event_type": "ZONE_ENTER",
                            "timestamp": timestamp,
                            "zone_id": zone_id,
                            "is_staff": is_staff,
                            "confidence": float(track.confidence),
                            "metadata": {"bbox": track.bbox}
                        }
                        if "checkout" in zone_id or "billing" in zone_id:
                            queue_event = enter_event.copy()
                            queue_event["event_type"] = "BILLING_QUEUE_JOIN"
                            self.pipeline_engine.emitter.emit(queue_event)
                            self._post_event_to_api(queue_event)
                        self.pipeline_engine.emitter.emit(enter_event)
                        self._post_event_to_api(enter_event)
                    elif transition_type == "ZONE_EXIT":
                        dwell_duration_ms = self.pipeline_engine.dwell_tracker.process_zone_exit(track_id, zone_id)
                        exit_event = {
                            "store_id": self.pipeline_engine.store_id,
                            "camera_id": self.pipeline_engine.camera_id,
                            "visitor_id": visitor_id,
                            "event_type": "ZONE_EXIT",
                            "timestamp": timestamp,
                            "zone_id": zone_id,
                            "dwell_ms": int(dwell_duration_ms),
                            "is_staff": is_staff,
                            "confidence": float(track.confidence),
                            "metadata": {"bbox": track.bbox}
                        }
                        self.pipeline_engine.emitter.emit(exit_event)
                        self._post_event_to_api(exit_event)
                        
            # Clean and process lost tracks inside the Occlusion engine
            lost_tracks = [t for t in tracks if t.lifecycle == "removed" or t.lifecycle == "lost"]
            self.occlusion_engine.process_lost_tracks(lost_tracks, timestamp, active_zones_mapping)
            
            for track in tracks:
                if track.lifecycle == "removed":
                    track_id = track.track_id
                    visitor_id = self.pipeline_engine.shopper_ids.pop(track_id, track_id)
                    forced_transitions = self.pipeline_engine.zone_manager.force_visitor_exit(track_id)
                    for transition_type, zone_id in forced_transitions:
                        dwell_duration_ms = self.pipeline_engine.dwell_tracker.process_zone_exit(track_id, zone_id)
                        exit_event = {
                            "store_id": self.pipeline_engine.store_id,
                            "camera_id": self.pipeline_engine.camera_id,
                            "visitor_id": visitor_id,
                            "event_type": "ZONE_EXIT",
                            "timestamp": timestamp,
                            "zone_id": zone_id,
                            "dwell_ms": int(dwell_duration_ms),
                            "confidence": float(track.confidence),
                            "metadata": {"bbox": track.bbox, "reason": "lost"}
                        }
                        self.pipeline_engine.emitter.emit(exit_event)
                        self._post_event_to_api(exit_event)
                    self.pipeline_engine.dwell_tracker.clear_track_records(track_id)
                    
            self.heatmap_points = self.heatmap_points[-400:]
            
            # Render overlays on two distinct copies
            annotated_standard = cv2.resize(frame, (640, 480))
            annotated_standard = self.pipeline_engine.visualizer.draw_annotations(
                frame=annotated_standard,
                tracks=tracks,
                current_zones=active_zones_mapping,
                dwells=dwells,
                occlusion_engine=self.occlusion_engine
            )

            
            annotated_heatmap = cv2.resize(frame, (640, 480))
            annotated_heatmap = self.pipeline_engine.visualizer.draw_heatmap_overlay(annotated_heatmap, self.heatmap_points)
            
            # Compress to JPEGs
            ret, jpeg_standard = cv2.imencode('.jpg', annotated_standard)
            if ret:
                self.latest_standard_frame = jpeg_standard.tobytes()
                
            ret, jpeg_heatmap = cv2.imencode('.jpg', annotated_heatmap)
            if ret:
                self.latest_heatmap_frame = jpeg_heatmap.tobytes()
                
            # Sleep to match camera source FPS
            time.sleep(0.015)

    def get_live_telemetry(self) -> dict:
        if not self.pipeline_engine or not self.pipeline_engine.tracker:
            return {
                "active_visitors": 0,
                "queue_size": 0,
                "avg_active_dwell": 0,
                "suspicious_count": 0,
                "occupancies": {}
            }
            
        tracks = self.pipeline_engine.tracker.tracks.values()
        active_tracks = [t for t in tracks if t.lifecycle == "active"]
        active_visitors = len(active_tracks)
        
        active_zones_mapping = {}
        dwells = {}
        for track in active_tracks:
            track_id = track.track_id
            active_zone = self.pipeline_engine.zone_manager.active_visitor_zones.get(track_id)
            if active_zone:
                active_zones_mapping[track_id] = active_zone
                entry_time = self.pipeline_engine.dwell_tracker.entry_times.get((track_id, active_zone))
                if entry_time:
                    dwells[track_id] = int(time.time() - entry_time)
                    
        queue_size = len([t_id for t_id, z in active_zones_mapping.items() if "checkout" in z or "billing" in z])
        avg_active_dwell = sum(dwells.values()) / (len(dwells) or 1)
        suspicious_count = len([t_id for t_id, d in dwells.items() if d > 45])
        
        occupancies = {}
        for t_id, z in active_zones_mapping.items():
            occupancies[z] = occupancies.get(z, 0) + 1
            
        return {
            "active_visitors": active_visitors,
            "queue_size": queue_size,
            "avg_active_dwell": int(avg_active_dwell),
            "suspicious_count": suspicious_count,
            "occupancies": occupancies
        }

# Global streamers pool
streamers: Dict[str, BackgroundPipelineStreamer] = {}

def get_streamer(store_id: str) -> BackgroundPipelineStreamer:
    if store_id not in streamers:
        streamers[store_id] = BackgroundPipelineStreamer(store_id)
        streamers[store_id].start()
    return streamers[store_id]
