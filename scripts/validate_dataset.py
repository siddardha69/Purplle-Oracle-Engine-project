import os
import sys
import json
import csv
from datetime import datetime
from pathlib import Path
from loguru import logger

# Add project root directory to path to enable module imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

try:
    import cv2
except ImportError:
    cv2 = None

from configs.settings import settings

def validate_videos() -> list:
    """
    Validates all MP4/AVI videos inside the videos directory using OpenCV.
    """
    video_dir = Path(settings.VIDEO_DIR)
    results = []
    
    if not video_dir.exists():
        logger.error(f"Videos directory does not exist: {video_dir}")
        return [{"file": str(video_dir), "valid": False, "error": "Directory missing"}]
        
    video_files = list(video_dir.glob("*.mp4")) + list(video_dir.glob("*.avi"))
    logger.info(f"Scanning videos directory... Found {len(video_files)} CCTV videos.")
    
    for v_file in video_files:
        meta = {
            "filename": v_file.name,
            "path": str(v_file),
            "valid": False,
            "fps": 0,
            "width": 0,
            "height": 0,
            "duration_s": 0.0,
            "frame_count": 0,
            "codec": "",
            "errors": []
        }
        
        # Check readability
        if not os.access(v_file, os.R_OK):
            meta["errors"].append("File not readable due to permission restrictions.")
            results.append(meta)
            continue
            
        if cv2 is None:
            meta["errors"].append("OpenCV library not installed. Skipping deep video frame checks.")
            meta["valid"] = True
            results.append(meta)
            continue
            
        try:
            cap = cv2.VideoCapture(str(v_file))
            if not cap.isOpened():
                meta["errors"].append("Failed to decode video container with OpenCV decoders.")
                results.append(meta)
                continue
                
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Read codec fourcc
            fourcc_val = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec = "".join([chr((fourcc_val >> 8 * i) & 0xFF) for i in range(4)])
            
            cap.release()
            
            meta["fps"] = round(fps, 2)
            meta["width"] = width
            meta["height"] = height
            meta["frame_count"] = frame_count
            meta["codec"] = codec
            
            if fps > 0:
                meta["duration_s"] = round(frame_count / fps, 1)
            else:
                meta["errors"].append("FPS calculated as zero. Dynamic timestamps cannot be inferred.")
                
            if width <= 0 or height <= 0:
                meta["errors"].append("Invalid frame resolution sizes.")
                
            if not meta["errors"]:
                meta["valid"] = True
                
        except Exception as e:
            meta["errors"].append(f"Unexpected OpenCV decode crash: {e}")
            
        results.append(meta)
        
    return results

def validate_layouts() -> list:
    """
    Validates all JSON layouts inside Layouts/Data directory.
    """
    layout_dir = Path(settings.LAYOUT_DIR)
    results = []
    
    # Create the directory if it's missing
    layout_dir.mkdir(parents=True, exist_ok=True)
    
    # Look for layout files
    layout_files = list(layout_dir.glob("*.json"))
    
    # Check if we should also check the base layout inside data/store_layout.json
    base_layout = Path("./data/store_layout.json")
    if base_layout.exists() and base_layout not in layout_files:
        layout_files.append(base_layout)
        
    logger.info(f"Scanning store layouts... Found {len(layout_files)} configuration files.")
    
    for l_file in layout_files:
        meta = {
            "filename": l_file.name,
            "path": str(l_file),
            "valid": False,
            "zones_count": 0,
            "errors": []
        }
        
        try:
            with open(l_file, "r") as f:
                data = json.load(f)
                
            if "zones" not in data:
                meta["errors"].append("Missing required root key: 'zones'")
                results.append(meta)
                continue
                
            zones = data["zones"]
            if not isinstance(zones, dict):
                meta["errors"].append("'zones' must be a dictionary map of key zone names to coordinate points lists.")
                results.append(meta)
                continue
                
            meta["zones_count"] = len(zones)
            
            # Loop through zones vertices
            for z_name, vertices in zones.items():
                if not isinstance(vertices, list) or len(vertices) < 3:
                    meta["errors"].append(f"Zone '{z_name}' coordinate list must contain at least 3 vertices (Got: {vertices})")
                    continue
                    
                for idx, pt in enumerate(vertices):
                    if not isinstance(pt, list) or len(pt) != 2:
                        meta["errors"].append(f"Zone '{z_name}' vertex {idx} must be a 2D float list coordinate [x, y]")
                        
            if not meta["errors"]:
                meta["valid"] = True
                
        except json.JSONDecodeError as jde:
            meta["errors"].append(f"Invalid JSON file format structure: {jde}")
        except Exception as e:
            meta["errors"].append(f"Failed to read layout configuration: {e}")
            
        results.append(meta)
        
    return results

def validate_pos() -> list:
    """
    Validates all CSV transaction ledgers inside pos directory.
    """
    pos_dir = Path(settings.POS_DIR)
    results = []
    
    # Create if missing
    pos_dir.mkdir(parents=True, exist_ok=True)
    
    pos_files = list(pos_dir.glob("*.csv"))
    
    # Check if we should also check the base pos transactions
    base_pos = Path("./data/pos_transactions.csv")
    if base_pos.exists() and base_pos not in pos_files:
        pos_files.append(base_pos)
        
    logger.info(f"Scanning POS transaction ledgers... Found {len(pos_files)} files.")
    
    for p_file in pos_files:
        meta = {
            "filename": p_file.name,
            "path": str(p_file),
            "valid": False,
            "total_rows": 0,
            "missing_values": 0,
            "duplicate_txn_ids": 0,
            "errors": []
        }
        
        try:
            with open(p_file, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                
                # Check required fields
                required = ["transaction_id", "store_id", "timestamp", "amount_inr"]
                missing_headers = [r for r in required if r not in headers]
                
                if missing_headers:
                    meta["errors"].append(f"Missing required CSV columns headers: {missing_headers}")
                    results.append(meta)
                    continue
                    
                seen_txn_ids = set()
                row_count = 0
                missing_val_count = 0
                dup_count = 0
                
                for row_idx, row in enumerate(reader, start=2):
                    row_count += 1
                    
                    # Inspect values
                    txn_id = row.get("transaction_id", "").strip()
                    store_id = row.get("store_id", "").strip()
                    raw_ts = row.get("timestamp", "").strip()
                    raw_amount = row.get("amount_inr", "").strip()
                    
                    if not txn_id or not store_id or not raw_ts or not raw_amount:
                        missing_val_count += 1
                        
                    if txn_id:
                        if txn_id in seen_txn_ids:
                            dup_count += 1
                        seen_txn_ids.add(txn_id)
                        
                    # Validate timestamp ISO-8601
                    if raw_ts:
                        try:
                            clean_ts = raw_ts.replace("Z", "")
                            if "T" in clean_ts:
                                datetime.fromisoformat(clean_ts)
                            else:
                                datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S")
                        except Exception:
                            meta["errors"].append(f"Row {row_idx}: Invalid date-time string format '{raw_ts}'. Expects ISO-8601.")
                            
                meta["total_rows"] = row_count
                meta["missing_values"] = missing_val_count
                meta["duplicate_txn_ids"] = dup_count
                
                if dup_count > 0:
                    meta["errors"].append(f"Found {dup_count} duplicate transaction IDs in file.")
                    
                if not meta["errors"]:
                    meta["valid"] = True
                    
        except Exception as e:
            meta["errors"].append(f"Unexpected file error reading POS transaction CSV: {e}")
            
        results.append(meta)
        
    return results

def run_validation_suite() -> dict:
    """
    Orchestrates the complete dataset validations checks and outputs a report.
    """
    logger.info("Executing dataset validation suite...")
    
    videos_res = validate_videos()
    layouts_res = validate_layouts()
    pos_res = validate_pos()
    
    # Assess overall status
    all_valid = True
    errors_list = []
    
    for v in videos_res:
        if not v["valid"]:
            all_valid = False
            errors_list.extend(v["errors"])
            
    for l in layouts_res:
        if not l["valid"]:
            all_valid = False
            errors_list.extend(l["errors"])
            
    for p in pos_res:
        if not p["valid"]:
            all_valid = False
            errors_list.extend(p["errors"])
            
    overall_status = "PASSED" if all_valid else "FAILED"
    if not all_valid and not errors_list:
        errors_list.append("Validation failed due to missing or unreadable source data files.")
        
    report = {
        "overall_status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "validation_summary": {
            "videos": {
                "total_scanned": len(videos_res),
                "valid": sum(1 for v in videos_res if v["valid"]),
                "details": videos_res
            },
            "layouts": {
                "total_scanned": len(layouts_res),
                "valid": sum(1 for l in layouts_res if l["valid"]),
                "details": layouts_res
            },
            "pos": {
                "total_scanned": len(pos_res),
                "valid": sum(1 for p in pos_res if p["valid"]),
                "details": pos_res
            }
        },
        "errors": errors_list
    }
    
    # Store Report in data/validation/dataset_report.json
    report_path = Path(settings.VALIDATION_DIR) / "dataset_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        
    logger.info(f"Dataset validation completed successfully. Status: {overall_status} | Saved to {report_path}")
    
    # Update dataset_registry.json validation status
    registry_path = Path("./data/metadata/dataset_registry.json")
    if registry_path.exists():
        try:
            with open(registry_path, "r") as rf:
                reg_data = json.load(rf)
                
            reg_data["last_updated"] = datetime.utcnow().isoformat() + "Z"
            reg_data["validation"]["status"] = overall_status
            reg_data["validation"]["last_validated"] = datetime.utcnow().isoformat() + "Z"
            reg_data["validation"]["errors"] = errors_list
            
            # Map files
            reg_data["videos"] = [v["filename"] for v in videos_res]
            reg_data["layouts"] = [l["filename"] for l in layouts_res]
            reg_data["pos_sources"] = [p["filename"] for p in pos_res]
            
            with open(registry_path, "w") as wf:
                json.dump(reg_data, wf, indent=2)
        except Exception as reg_err:
            logger.error(f"Failed to update dataset registry checkpoints: {reg_err}")
            
    return report

if __name__ == "__main__":
    run_validation_suite()
