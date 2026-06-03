import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
from app.services.base import BaseService
from configs.settings import settings
from scripts.validate_dataset import run_validation_suite

class DatasetLoaderService(BaseService):
    """
    Ingestion layer orchestrating dataset registration, validations, and loading
    prior to computer vision pipelines execution runs.
    """

    def load_videos(self) -> List[Path]:
        """
        Locates all readable CCTV videography streams.
        """
        video_dir = Path(settings.VIDEO_DIR)
        if not video_dir.exists():
            return []
        return list(video_dir.glob("*.mp4")) + list(video_dir.glob("*.avi"))

    def load_layout(self, filename: str = "store_layout.json") -> Optional[Dict[str, Any]]:
        """
        Loads store polygonal zones coordinate definitions.
        """
        layout_dir = Path(settings.LAYOUT_DIR)
        path = layout_dir / filename
        
        # Fallback to local data folder if custom layouts folder is clean
        if not path.exists():
            path = Path("./data/store_layout.json")
            
        if not path.exists():
            logger.error(f"Layout definition file not found: {path}")
            return None
            
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load layout JSON from {path}: {e}")
            return None

    def load_pos_transactions(self, filename: str = "pos_transactions.csv") -> int:
        """
        Invokes the POSIngestionService to import rows into database structures.
        """
        from app.services.pos_ingestion import POSIngestionService
        
        pos_dir = Path(settings.POS_DIR)
        path = pos_dir / filename
        
        if not path.exists():
            path = Path("./data/pos_transactions.csv")
            
        if not path.exists():
            logger.error(f"POS Transactions CSV not found: {path}")
            return 0
            
        ingestor = POSIngestionService(db=self.db)
        return ingestor.ingest_pos_csv(str(path))

    def register_dataset(self) -> Dict[str, Any]:
        """
        Registers local assets in the dataset registry tracking configuration files.
        """
        registry_path = Path("./data/metadata/dataset_registry.json")
        if not registry_path.exists():
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            
        videos = [p.name for p in self.load_videos()]
        
        # Load layout files
        layout_dir = Path(settings.LAYOUT_DIR)
        layouts = [p.name for p in layout_dir.glob("*.json")]
        if Path("./data/store_layout.json").exists() and "store_layout.json" not in layouts:
            layouts.append("store_layout.json")
            
        # Load pos files
        pos_dir = Path(settings.POS_DIR)
        pos_sources = [p.name for p in pos_dir.glob("*.csv")]
        if Path("./data/pos_transactions.csv").exists() and "pos_transactions.csv" not in pos_sources:
            pos_sources.append("pos_transactions.csv")
            
        # Standard structure
        registry = {
            "last_updated": Path(registry_path).stat().st_mtime if registry_path.exists() else 0.0,
            "videos": videos,
            "layouts": layouts,
            "pos_sources": pos_sources,
            "validation": {
                "status": "PENDING",
                "last_validated": None,
                "errors": []
            },
            "processing": {
                "status": "READY" if videos and layouts else "MISSING_DATA",
                "last_run": None
            }
        }
        
        try:
            with open(registry_path, "w") as f:
                json.dump(registry, f, indent=2)
            logger.info("Ingestion registry checkpoint created.")
        except Exception as e:
            logger.error(f"Failed to write registry metadata: {e}")
            
        return registry

    def validate_before_run(self) -> bool:
        """
        Runs comprehensive validation sweeps. Returns True if execution is safe.
        """
        logger.info("Executing dataset validation checks before pipeline trigger...")
        report = run_validation_suite()
        
        status = report.get("overall_status", "FAILED")
        if status == "PASSED":
            logger.info("Dataset validation checks passed! Pipeline execution is safe to boot.")
            return True
            
        logger.error(f"Dataset validation checks failed. Blockers found: {report.get('errors', [])}")
        return False
