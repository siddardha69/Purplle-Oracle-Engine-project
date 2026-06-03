import os
import sys
import json
from pathlib import Path

# Add project root directory to path to enable module imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from configs.settings import settings

def inspect_workspace():
    """
    Scans ingestion directories and prints a human-readable summary of the datasets.
    """
    print("=" * 60)
    print("        [DATA] PURPLLE DATASET INSPECTION DASHBOARD")
    print("=" * 60)
    
    # 1. Inspect CCTV Videos
    video_dir = Path(settings.VIDEO_DIR)
    v_files = list(video_dir.glob("*.mp4")) + list(video_dir.glob("*.avi"))
    print(f"\n[VIDEO] CCTV VIDEOS FOUND: {len(v_files)}")
    print("-" * 40)
    for idx, v in enumerate(v_files, start=1):
        size_mb = os.path.getsize(v) / (1024 * 1024)
        print(f"  {idx}. {v.name} ({size_mb:.2f} MB)")
        
    # 2. Inspect Store Layouts
    layout_dir = Path(settings.LAYOUT_DIR)
    l_files = list(layout_dir.glob("*.json"))
    base_layout = Path("./data/store_layout.json")
    if base_layout.exists() and base_layout not in l_files:
        l_files.append(base_layout)
        
    print(f"\n[LAYOUT] STORE LAYOUTS CONFIGS FOUND: {len(l_files)}")
    print("-" * 40)
    for idx, l in enumerate(l_files, start=1):
        try:
            with open(l, "r") as f:
                data = json.load(f)
            zones = list(data.get("zones", {}).keys())
            print(f"  {idx}. {l.name} | Zones Found ({len(zones)}): {zones}")
        except Exception as e:
            print(f"  {idx}. {l.name} | [ERROR: {e}]")
            
    # 3. Inspect POS Transactions
    pos_dir = Path(settings.POS_DIR)
    pos_files = list(pos_dir.glob("*.csv"))
    base_pos = Path("./data/pos_transactions.csv")
    if base_pos.exists() and base_pos not in pos_files:
        pos_files.append(base_pos)
        
    print(f"\n[POS] POS TRANSACTION LEDGERS FOUND: {len(pos_files)}")
    print("-" * 40)
    for idx, p in enumerate(pos_files, start=1):
        try:
            with open(p, "r", encoding="utf-8") as f:
                row_count = sum(1 for _ in f) - 1
            size_kb = os.path.getsize(p) / 1024
            print(f"  {idx}. {p.name} | Total Rows: {row_count} | Size: {size_kb:.1f} KB")
        except Exception as e:
            print(f"  {idx}. {p.name} | [ERROR: {e}]")
            
    # 4. Ingest and print Registry Status
    registry_path = Path("./data/metadata/dataset_registry.json")
    print(f"\n[REGISTRY] INGESTION REGISTRY STATUS:")
    print("-" * 40)
    if registry_path.exists():
        try:
            with open(registry_path, "r") as f:
                reg = json.load(f)
            print(f"  Last Updated    : {reg.get('last_updated', 'N/A')}")
            print(f"  Validation State: {reg.get('validation', {}).get('status', 'PENDING')}")
            print(f"  Last Validated  : {reg.get('validation', {}).get('last_validated', 'N/A')}")
            print(f"  Ingested Errors : {len(reg.get('validation', {}).get('errors', []))} issues identified.")
        except Exception as e:
            print(f"  Failed to read registry: {e}")
    else:
        print("  Ingestion registry is currently offline.")
        
    print("\n" + "=" * 60)

if __name__ == "__main__":
    inspect_workspace()
