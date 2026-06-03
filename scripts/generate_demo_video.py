import os
import sys
import cv2
from pathlib import Path

# Add project root directory to path to enable module imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Set environment variable to run in sqlite fallback mode for the loader
os.environ["DATABASE_URL"] = "sqlite:///./store_intelligence.db"

from pipeline.main import RetailVisionPipeline
from pipeline.config import pipeline_settings

def generate_demo():
    print("Initializing demo generation pipeline...")
    # Override settings
    pipeline_settings.RENDER_VISUALS = True
    pipeline_settings.DEBUG_MODE = False
    
    # Locate video file
    video_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "videos")
    video_path = os.path.join(video_dir, "CAM 4.mp4")
    if not os.path.exists(video_path):
        video_path = os.path.join(video_dir, "CAM 1.mp4") # Fallback
    
    print(f"Loading source video: {video_path}")
    pipeline = RetailVisionPipeline()
    # Explicitly configure the video loader to use our specific path
    from pipeline.video_loader import VideoLoader
    pipeline.loader = VideoLoader(video_path=video_path)
    
    # Configure video writer
    output_path = os.path.join(video_dir, "demo_processed.mp4")
    print(f"Configuring output video writer at: {output_path}")
    
    # We resize to 640x480 for the dashboard
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, 20.0, (640, 480))
    
    frame_count = 0
    max_frames = 150  # 7.5 seconds of demo video at 20 FPS (ideal for quick loading and looping)
    
    try:
        for frame_idx, timestamp, frame in pipeline.loader.iter_frames():
            frame_count += 1
            if frame_count > max_frames:
                break
                
            # 1. Object Detections (YOLO)
            detections = pipeline.detector.detect(frame)
            
            # Normalize coordinates
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
            
            # 2. Tracks Detections
            tracks = pipeline.tracker.update(normalized_detections)
            
            # Keep active zones map
            active_zones_mapping = {}
            for track in tracks:
                if track.lifecycle == "active":
                    x1, y1, x2, y2 = track.bbox
                    cx = (x1 + x2) / 2.0
                    cy = y2
                    active_zone = pipeline.zone_manager.active_visitor_zones.get(track.track_id)
                    if active_zone:
                        active_zones_mapping[track.track_id] = active_zone
                        
            # Update Occlusion Engine
            pipeline.occlusion_engine.update(tracks, timestamp, active_zones_mapping)
            
            # Process tracks to update pipeline state (crossing line, enter/exit, etc.)
            for track in tracks:
                if track.lifecycle != "active":
                    continue
                visitor_id, is_reentry = pipeline.get_unified_shopper_id(track, timestamp)
                pipeline.tracker.check_line_crossing(track)
                x1, y1, x2, y2 = track.bbox
                cx = (x1 + x2) / 2.0
                cy = y2
                pipeline.zone_manager.evaluate_visitor_position(track.track_id, cx, cy)
                
            # Resize frame to 640x480
            annotated_frame = cv2.resize(frame, (640, 480))
            
            # Draw visual annotations (YOLO boxes, tracks, zones, etc.)
            annotated_frame = pipeline.visualizer.draw_annotations(
                frame=annotated_frame,
                tracks=tracks,
                current_zones=active_zones_mapping,
                occlusion_engine=pipeline.occlusion_engine
            )
            
            # Write to output file
            out.write(annotated_frame)
            if frame_count % 20 == 0:
                print(f"Processed frame {frame_count}/{max_frames}...")
                
    except Exception as e:
        print(f"Error during generation: {e}")
    finally:
        out.release()
        print(f"Demo generation completed. Output saved to: {output_path}")

if __name__ == "__main__":
    generate_demo()
