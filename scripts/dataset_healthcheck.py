import sys
import json
from pathlib import Path

# Add project root directory to path to enable module imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from configs.settings import settings

def run_healthcheck():
    """
    Checks the validation report status and outputs clean terminal exit codes.
    READY (0) - Ready for stream processing.
    WARNING (1) - Data present but has formatting issues.
    FAILED (2) - Hard blockers or data files missing.
    """
    report_path = Path(settings.VALIDATION_DIR) / "dataset_report.json"
    
    if not report_path.exists():
        print("=" * 60)
        print("[HEALTH] DATASET HEALTH STATUS: FAILED")
        print("=" * 60)
        print("  Reason: Validation report file not found on disk.")
        print("  Action: Run 'python scripts/validate_dataset.py' to generate.")
        sys.exit(2)
        
    try:
        with open(report_path, "r") as f:
            report = json.load(f)
            
        status = report.get("overall_status", "FAILED")
        errors = report.get("errors", [])
        
        print("=" * 60)
        print(f"[HEALTH] DATASET HEALTH STATUS: {status}")
        print("=" * 60)
        print(f"  Last Validated: {report.get('timestamp', 'N/A')}")
        
        if status == "PASSED":
            print("  Status detail : All CCTV streams, layout polygon vertices, and POS CSV")
            print("                  transaction registries validated successfully.")
            print("  Outcome       : READY. Execution pipeline is safe to boot.")
            sys.exit(0)
        else:
            print("  Hard Blockers identified:")
            for idx, err in enumerate(errors, start=1):
                print(f"    {idx}. {err}")
            print("\n  Outcome       : FAILED. Aborting launch to prevent analytical corruption.")
            sys.exit(2)
            
    except Exception as e:
        print("=" * 60)
        print("[HEALTH] DATASET HEALTH STATUS: FAILED")
        print("=" * 60)
        print(f"  Failed to read health check reports: {e}")
        sys.exit(2)

if __name__ == "__main__":
    run_healthcheck()
