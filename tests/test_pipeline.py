import os
import json
import time
import pytest
from pipeline.config import pipeline_settings
from pipeline.video_loader import VideoLoader
from pipeline.detect import PersonDetector
from pipeline.tracker import MultiObjectTracker, TrackState
from pipeline.zones import ZoneManager, PolygonZone, DwellTracker
from pipeline.reid import ReEntryManager
from pipeline.events import PurplleStoreEvent
from pipeline.event_emitter import EventEmitter

def test_video_loader_timestamp_timeline():
    """
    Asserts VideoLoader calculates correct ISO 8601 relative time increments.
    """
    # Create simple instance (raises error on init if file missing, let's mock it if needed
    # or test the generate_frame_timestamp directly since it only needs arithmetic!)
    # To bypass mock file raises during tests, we catch or test the method directly on a mock sub-class
    class MockVideoLoader(VideoLoader):
        def __init__(self):
            self.fps = 25.0
            
    loader = MockVideoLoader()
    ts0 = loader.generate_frame_timestamp(0)
    ts25 = loader.generate_frame_timestamp(25)
    
    assert ts0.endswith(".000Z")
    assert "2026-06-01T07:40:00" in ts0
    assert "2026-06-01T07:40:01" in ts25  # 25 frames later at 25fps represents 1s offset

def test_person_detector_simulated_outputs():
    """
    Asserts PersonDetector outputs COCO-compliant track-ready detections.
    """
    detector = PersonDetector(model_path="yolov8n.pt")
    detector.is_simulation = True # Force simulated fallback
    
    detections = detector.detect(None)
    assert len(detections) > 0
    bbox, conf, cls_id = detections[0]
    
    assert len(bbox) == 4 # [x1, y1, x2, y2]
    assert conf > 0.0
    assert cls_id == 0 # COCO person index

def test_tracker_line_crossing_gate_intersection():
    """
    Asserts MultiObjectTracker identifies virtual line crossing transitions.
    """
    tracker = MultiObjectTracker()
    
    # Configure mock crossing line at y = 300
    tracker.line_start = (0.0, 300.0)
    tracker.line_end = (600.0, 300.0)
    
    # Shopper moving from y = 280 to y = 320 (Crossing downwards/inwards -> ENTRY)
    track = TrackState("TRK-0001", [100.0, 180.0, 150.0, 280.0], 0.95)
    tracker.tracks["TRK-0001"] = track
    tracker.triggered_events["TRK-0001"] = set()
    
    # Step 2: Update coordinate crossing over line (foot centroid represents y2 bottom edge)
    track.update([100.0, 220.0, 150.0, 320.0], 0.95)
    
    crossing = tracker.check_line_crossing(track)
    assert crossing == "ENTRY"
    
    # Shopper moving from y = 320 to y = 280 (Crossing upwards/outwards -> EXIT)
    track_exit = TrackState("TRK-0002", [200.0, 220.0, 250.0, 320.0], 0.90)
    tracker.tracks["TRK-0002"] = track_exit
    tracker.triggered_events["TRK-0002"] = set()
    
    track_exit.update([200.0, 180.0, 250.0, 280.0], 0.90)
    
    crossing_exit = tracker.check_line_crossing(track_exit)
    assert crossing_exit == "EXIT"

def test_spatial_polygon_zones_containment():
    """
    Asserts PolygonZone containing checks isolate shopper positions.
    """
    vertices = [[0, 0], [0, 100], [100, 100], [100, 0]]
    zone = PolygonZone("makeup_aisle", vertices)
    
    # Centroid standing location: (50, 50) represents standing in the aisle
    assert zone.contains_point(50.0, 50.0) is True
    # Centroid: (150, 50) represents standing in the neighboring aisle
    assert zone.contains_point(150.0, 50.0) is False

def test_loitering_dwell_tracker_schedules():
    """
    Asserts DwellTracker calculates loitering times and schedules ZONE_DWELL every 30s.
    """
    dwell = DwellTracker()
    dwell.dwell_interval_s = 0.5 # Set interval to 500ms to avoid test sleep freezes
    
    track_id = "TRK-0001"
    zone_id = "lipstick_aisle"
    
    dwell.process_zone_entry(track_id, zone_id)
    
    # Immediately checking shouldn't trigger loitering DWELL warnings
    assert dwell.check_for_dwell_events(track_id, zone_id) is None
    
    # Wait for interval to elapse
    time.sleep(0.6)
    
    duration = dwell.check_for_dwell_events(track_id, zone_id)
    assert duration is not None
    assert duration >= 500.0 # Exceeded 500ms bounds
    
    # Exiting pops timing registers
    total_stay = dwell.process_zone_exit(track_id, zone_id)
    assert total_stay >= 600.0

def test_lightweight_reid_appearance_and_time_matching():
    """
    Asserts ReEntryManager maps returning shopper tracks to persistent shopper IDs.
    """
    reid = ReEntryManager()
    reid.time_window = 2.0 # 2 seconds
    reid.max_distance = 50.0
    reid.aspect_ratio_tolerance = 0.15
    
    track_id = "TRK-0001"
    # Create shopper trace snapshot at coordinate (100, 100)
    # Bounding box: x1=80, y1=20, x2=120, y2=100 (Width=40, Height=80 -> Aspect Ratio = 0.5)
    reid.register_lost_track(
        track_id=track_id,
        last_centroid=(100.0, 100.0),
        last_bbox=[80.0, 20.0, 120.0, 100.0]
    )
    
    # Match candidate 1: Same aspect ratio (0.5), close spatial location (110, 110), within time window
    # Bounding box: x1=90, y1=30, x2=130, y2=110
    matched_id = reid.check_for_reentry(
        new_track_id="TRK-0002",
        new_centroid=(110.0, 110.0),
        new_bbox=[90.0, 30.0, 130.0, 110.0]
    )
    assert matched_id == "TRK-0001" # ReID successfully unified returning visitor trace ID
    
    # Match candidate 2: Different aspect ratio (1.0), should fail matching
    reid.register_lost_track(
        track_id="TRK-0003",
        last_centroid=(200.0, 200.0),
        last_bbox=[150.0, 100.0, 250.0, 200.0] # Width=100, Height=100 -> Aspect Ratio = 1.0
    )
    
    mismatch_id = reid.check_for_reentry(
        new_track_id="TRK-0004",
        new_centroid=(210.0, 210.0),
        new_bbox=[180.0, 160.0, 220.0, 240.0] # Width=40, Height=80 -> Aspect Ratio = 0.5
    )
    assert mismatch_id is None

def test_events_pydantic_schema_validation():
    """
    Asserts PurplleStoreEvent validations check timestamps, event types, and serializations.
    """
    event_data = {
        "store_id": "STORE-DLF-01",
        "camera_id": "CAM-MAIN-01",
        "visitor_id": "TRK-0001",
        "event_type": "ZONE_ENTER",
        "timestamp": "2026-06-01T10:00:00.123Z",
        "zone_id": "makeup_zone",
        "confidence": 0.95,
        "metadata": {"bbox": [10, 20, 30, 40]}
    }
    
    event = PurplleStoreEvent(**event_data)
    assert event.event_type == "ZONE_ENTER"
    assert event.event_id is not None
    
    # Check JSONL serialization outputs clean single line strings
    line = event.to_jsonl_line()
    assert "makeup_zone" in line
    assert "2026-06-01T10:00:00.123Z" in line

def test_event_emitter_jsonl_append(tmp_path):
    """
    Asserts EventEmitter writes validated JSON strings to flat JSONL files.
    """
    output_file = tmp_path / "events.jsonl"
    emitter = EventEmitter(output_path=str(output_file))
    
    event_data = {
        "store_id": "STORE-DLF-01",
        "camera_id": "CAM-MAIN-01",
        "visitor_id": "TRK-0001",
        "event_type": "ENTRY",
        "timestamp": "2026-06-01T10:00:00.000Z",
        "confidence": 0.98
    }
    
    success = emitter.emit(event_data)
    assert success is True
    
    # Read emitted line
    with open(output_file, "r") as f:
        lines = f.readlines()
        
    assert len(lines) == 1
    loaded = json.loads(lines[0])
    assert loaded["visitor_id"] == "TRK-0001"
    assert loaded["event_type"] == "ENTRY"
