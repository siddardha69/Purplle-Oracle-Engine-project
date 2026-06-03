import os
import sys
import time
from typing import Dict, Any, List, Tuple, Optional
from loguru import logger

# Append workspace to Python system path to facilitate global imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.config import pipeline_settings
from pipeline.video_loader import VideoLoader
from pipeline.detect import PersonDetector
from pipeline.tracker import MultiObjectTracker, TrackState
from pipeline.zones import ZoneManager, DwellTracker
from pipeline.reid import ReEntryManager
from pipeline.events import PurplleStoreEvent
from pipeline.event_emitter import EventEmitter
from pipeline.visualizer import Visualizer

class RetailVisionPipeline:
    """
    Unified Ingestion & Spatial Analytics Engine orchestrating YOLOv8 detectors,
    centroid trackers, virtual crossing gates, polygonal aisle managers, and lightweight ReIDs.
    """
    def __init__(self):
        logger.info("Initializing Purplle Retail Store Intelligence Pipeline...")
        
        # Ingest and validate data files before pipeline boot
        from app.services.dataset_loader import DatasetLoaderService
        from app.core.database import SessionLocal
        
        db_sess = SessionLocal()
        try:
            loader = DatasetLoaderService(db=db_sess)
            loader.register_dataset()
            if not loader.validate_before_run():
                logger.critical("Dataset Ingestion Precheck FAILED! CCTV pipeline boot sequence aborted.")
                sys.exit(1)
        except SystemExit:
            raise
        except Exception as precheck_err:
            logger.error(f"Error executing precheck validations: {precheck_err}")
        finally:
            db_sess.close()
            
        # Load unified settings
        self.store_id = pipeline_settings.STORE_ID
        self.camera_id = pipeline_settings.CAMERA_ID
        
        # Instantiate CV components
        self.loader = VideoLoader()
        self.detector = PersonDetector()
        self.tracker = MultiObjectTracker()
        self.zone_manager = ZoneManager()
        self.dwell_tracker = DwellTracker()
        self.reid_manager = ReEntryManager()
        self.emitter = EventEmitter()
        
        # Instantiate Occlusion Engine
        from pipeline.occlusion_engine import OcclusionIntelligenceEngine
        self.occlusion_engine = OcclusionIntelligenceEngine(self.store_id)
        
        # Reset JSONL logs output file before starting fresh video streams
        self.emitter.clear_output_file()
        
        self.visualizer = Visualizer(self.zone_manager.zones)
        
        # Active shopper tracking mapping to persistent unified ID: {track_id: shopper_id}
        self.shopper_ids: Dict[str, str] = {}

    def get_unified_shopper_id(self, track: TrackState, timestamp: str) -> Tuple[str, bool]:
        """
        Looks up persistent shopper tracking references. Checks ReID histories 
        for reappearance matching.
        Returns:
            Tuple: (visitor_id, is_reentry_triggered)
        """
        track_id = track.track_id
        
        # If already mapped, return cached ID
        if track_id in self.shopper_ids:
            return self.shopper_ids[track_id], False
            
        # Extract bottom standing ground center
        x1, y1, x2, y2 = track.bbox
        cx = (x1 + x2) / 2.0
        cy = y2
        
        # Run ReID history pool checks
        matched_shopper_id = self.reid_manager.check_for_reentry(
            new_track_id=track_id,
            new_centroid=(cx, cy),
            new_bbox=track.bbox
        )
        
        if matched_shopper_id:
            self.shopper_ids[track_id] = matched_shopper_id
            logger.info(f"Shopper {matched_shopper_id} triggered returning REENTRY event!")
            return matched_shopper_id, True
        else:
            # First time shopper entry. Assign track_id as base persistent shopper_id
            self.shopper_ids[track_id] = track_id
            return track_id, False

    def check_staff_classification(self, track: TrackState, active_zone: Optional[str]) -> bool:
        """
        Heuristic filter classifying store staff based on stay durations 
        or loitering inside private staff checkout zones.
        """
        # Rule 1: Loitering inside dedicated storage/restricted checkout areas for too long
        if active_zone == "checkout_zone" and len(track.history) > 300: # Over 300 frames
            return True
            
        # Rule 2: Shape proportions consistency (Staff often carry visual devices)
        # Placeholder for heuristic extension
        return False

    def run_pipeline(self):
        """
        Main runner sequence looping through CCTV frames, executing detection networks,
        evaluating transitions, and emitting structured Purplle event telemetry.
        """
        logger.info("Launching CCTV stream processing pipeline execution...")
        
        frame_count = 0
        start_time = time.time()
        
        try:
            for frame_idx, timestamp, frame in self.loader.iter_frames():
                frame_count += 1
                
                # Copy frame for debug overlay drawing
                annotated_frame = frame.copy() if pipeline_settings.RENDER_VISUALS else None
                
                # 1. Object Detections (YOLO)
                detections = self.detector.detect(frame)
                
                # Normalize coordinates to store_layout's 640x480 coordinate space
                frame_h, frame_w = frame.shape[:2]
                scale_x = 640.0 / frame_w
                scale_y = 480.0 / frame_h
                
                normalized_detections = []
                for bbox, conf, cls_id in detections:
                    x1, y1, x2, y2 = bbox
                    x1_scaled = x1 * scale_x
                    y1_scaled = y1 * scale_y
                    x2_scaled = x2 * scale_x
                    y2_scaled = y2 * scale_y
                    normalized_detections.append(([x1_scaled, y1_scaled, x2_scaled, y2_scaled], conf, cls_id))
                
                # 2. Tracks Detections (Centroids Euclidean Maps)
                tracks = self.tracker.update(normalized_detections)
                
                # Keep active zones map to render labels in visualizer
                active_zones_mapping = {}
                for track in tracks:
                    if track.lifecycle == "active":
                        x1, y1, x2, y2 = track.bbox
                        cx = (x1 + x2) / 2.0
                        cy = y2
                        active_zone = self.zone_manager.active_visitor_zones.get(track.track_id)
                        if active_zone:
                            active_zones_mapping[track.track_id] = active_zone
                            
                # Update Occlusion Engine Visibility Models in real-time
                self.occlusion_engine.update(tracks, timestamp, active_zones_mapping)
                
                for track in tracks:
                    track_id = track.track_id
                    
                    # Skip lost or removed tracks in frame-level processing
                    if track.lifecycle != "active":
                        continue
                        
                    # Unified ID evaluation (Unified Shopper ID & Re-entry check)
                    visitor_id, is_reentry = self.get_unified_shopper_id(track, timestamp)
                    
                    # Trigger Reentry Event if unified match was established on birth
                    if is_reentry:
                        reentry_event = {
                            "store_id": self.store_id,
                            "camera_id": self.camera_id,
                            "visitor_id": visitor_id,
                            "event_type": "REENTRY",
                            "timestamp": timestamp,
                            "confidence": float(track.confidence),
                            "metadata": {"bbox": track.bbox, "reassigned_track": track_id}
                        }
                        self.emitter.emit(reentry_event)
                    
                    # 3. Entry/Exit gate line intersection checks
                    crossing_type = self.tracker.check_line_crossing(track)
                    
                    if crossing_type == "ENTRY":
                        # Shopper crossed gate inwards!
                        entry_event = {
                            "store_id": self.store_id,
                            "camera_id": self.camera_id,
                            "visitor_id": visitor_id,
                            "event_type": "ENTRY",
                            "timestamp": timestamp,
                            "confidence": float(track.confidence),
                            "metadata": {"bbox": track.bbox}
                        }
                        self.emitter.emit(entry_event)
                        
                    elif crossing_type == "EXIT":
                        # Shopper crossed gate outwards!
                        # Clear track session mappings
                        exit_event = {
                            "store_id": self.store_id,
                            "camera_id": self.camera_id,
                            "visitor_id": visitor_id,
                            "event_type": "EXIT",
                            "timestamp": timestamp,
                            "confidence": float(track.confidence),
                            "metadata": {"bbox": track.bbox}
                        }
                        self.emitter.emit(exit_event)
                    
                    # 4. Polygonal zones evaluation
                    x1, y1, x2, y2 = track.bbox
                    cx = (x1 + x2) / 2.0
                    cy = y2
                    
                    zone_transitions = self.zone_manager.evaluate_visitor_position(track_id, cx, cy)
                    active_zone = self.zone_manager.active_visitor_zones.get(track_id)
                        
                    # Staff classifications heuristic
                    is_staff = self.check_staff_classification(track, active_zone)
                    
                    # Process zone transition events
                    for transition_type, zone_id in zone_transitions:
                        if transition_type == "ZONE_ENTER":
                            # Register entry time inside Dwell Tracker
                            self.dwell_tracker.process_zone_entry(track_id, zone_id)
                            
                            # Emit ZONE_ENTER event
                            enter_event = {
                                "store_id": self.store_id,
                                "camera_id": self.camera_id,
                                "visitor_id": visitor_id,
                                "event_type": "ZONE_ENTER",
                                "timestamp": timestamp,
                                "zone_id": zone_id,
                                "is_staff": is_staff,
                                "confidence": float(track.confidence),
                                "metadata": {"bbox": track.bbox}
                            }
                            
                            # If they enter checkout zone, trigger optional queue join warning
                            if "checkout" in zone_id or "billing" in zone_id:
                                queue_event = enter_event.copy()
                                queue_event["event_type"] = "BILLING_QUEUE_JOIN"
                                self.emitter.emit(queue_event)
                                
                            self.emitter.emit(enter_event)
                            
                        elif transition_type == "ZONE_EXIT":
                            # Pop entry time and calculate total stay duration
                            dwell_duration_ms = self.dwell_tracker.process_zone_exit(track_id, zone_id)
                            
                            # Emit ZONE_EXIT event
                            exit_event = {
                                "store_id": self.store_id,
                                "camera_id": self.camera_id,
                                "visitor_id": visitor_id,
                                "event_type": "ZONE_EXIT",
                                "timestamp": timestamp,
                                "zone_id": zone_id,
                                "dwell_ms": int(dwell_duration_ms),
                                "is_staff": is_staff,
                                "confidence": float(track.confidence),
                                "metadata": {"bbox": track.bbox}
                            }
                            self.emitter.emit(exit_event)
                            
                    # 5. Continuous Aisle loitering Dwell Checkups (Every 30 seconds)
                    if active_zone:
                        dwell_duration_ms = self.dwell_tracker.check_for_dwell_events(track_id, active_zone)
                        if dwell_duration_ms is not None:
                            dwell_event = {
                                "store_id": self.store_id,
                                "camera_id": self.camera_id,
                                "visitor_id": visitor_id,
                                "event_type": "ZONE_DWELL",
                                "timestamp": timestamp,
                                "zone_id": active_zone,
                                "dwell_ms": int(dwell_duration_ms),
                                "is_staff": is_staff,
                                "confidence": float(track.confidence),
                                "metadata": {"bbox": track.bbox}
                            }
                            self.emitter.emit(dwell_event)
                            
                # Process lost tracks in Occlusion intelligence engine
                lost_tracks = [t for t in tracks if t.lifecycle == "removed" or t.lifecycle == "lost"]
                self.occlusion_engine.process_lost_tracks(lost_tracks, timestamp, active_zones_mapping)
                
                # 6. Handle dropped tracks cleaning and ReID snapshots registers
                for track in tracks:
                    if track.lifecycle == "removed":
                        track_id = track.track_id
                        visitor_id = self.shopper_ids.pop(track_id, track_id)
                        
                        # Fetch active zone before clearing it
                        active_zone = self.zone_manager.active_visitor_zones.get(track_id)
                        
                        # 6a. Force exit out of polygonal zone if loitering
                        forced_transitions = self.zone_manager.force_visitor_exit(track_id)
                        for transition_type, zone_id in forced_transitions:
                            dwell_duration_ms = self.dwell_tracker.process_zone_exit(track_id, zone_id)
                            
                            exit_event = {
                                "store_id": self.store_id,
                                "camera_id": self.camera_id,
                                "visitor_id": visitor_id,
                                "event_type": "ZONE_EXIT",
                                "timestamp": timestamp,
                                "zone_id": zone_id,
                                "dwell_ms": int(dwell_duration_ms),
                                "confidence": float(track.confidence),
                                "metadata": {"bbox": track.bbox, "reason": "lost"}
                            }
                            self.emitter.emit(exit_event)
                            
                        # 6b. Buffer coordinates history snapshot to ReID matching pool
                        x1, y1, x2, y2 = track.bbox
                        cx = (x1 + x2) / 2.0
                        cy = y2
                        
                        self.reid_manager.register_lost_track(
                            track_id=track_id,
                            last_centroid=(cx, cy),
                            last_bbox=track.bbox
                        )
                        
                        # Sweep clean Dwell Tracker caches
                        self.dwell_tracker.clear_track_records(track_id)
                        
                # 7. Rendering overlays
                if pipeline_settings.RENDER_VISUALS and annotated_frame is not None:
                    import cv2
                    annotated_frame = cv2.resize(annotated_frame, (640, 480))
                    annotated_frame = self.visualizer.draw_annotations(
                        frame=annotated_frame,
                        tracks=tracks,
                        current_zones=active_zones_mapping,
                        occlusion_engine=self.occlusion_engine
                    )
                    
                    if pipeline_settings.DEBUG_MODE:
                        self.visualizer.display_frame(annotated_frame)
                        
                # Report frame processing rates stats
                if frame_count % 50 == 0:
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed
                    logger.info(f"CCTV Ingestion Status - Frame: {frame_count} | Speed: {fps:.1f} FPS")

        except KeyboardInterrupt:
            logger.info("CCTV Ingestion processing manually interrupted.")
        except Exception as e:
            logger.critical(f"CCTV pipeline execution crashed: {e}")
        finally:
            # Release visualizer windows
            if pipeline_settings.DEBUG_MODE:
                self.visualizer.close_all_windows()
            
            elapsed = time.time() - start_time
            logger.info(
                f"Pipeline session finalized. "
                f"Processed: {frame_count} frames | "
                f"Duration: {elapsed:.2f}s | "
                f"Avg Speed: {frame_count / (elapsed if elapsed > 0 else 1.0):.1f} FPS"
            )

def run_pipeline():
    """
    Main entrypoint launching the computer vision detection pipeline sequence.
    """
    pipeline = RetailVisionPipeline()
    pipeline.run_pipeline()

if __name__ == "__main__":
    run_pipeline()
