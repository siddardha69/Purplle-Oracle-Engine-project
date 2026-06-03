# 📊 Purplle Store Intelligence - Dataset Setup & Ingestion Guide

Welcome to the production-grade **Oracle Ingestion Engine** setup guide. Follow these instructions to ingest, inspect, and validate real CCTV video feeds, storefront boundary mappings, and cashier cash ledgers.

---

## 📁 Repository Directory Structure

Inputs are isolated inside the `data/` subdirectory:

```
data/
├── videos/          <-- Drop raw CCTV streams here (*.mp4, *.avi)
├── layouts/         <-- Drop store layout polygon coordinates here (*.json)
├── pos/             <-- Drop cashier ledger transaction files here (*.csv)
├── processed/       <-- Chunked frames and segments output
├── outputs/         <-- Output visual overlays and logs
├── validation/      <-- Structured validation reports (dataset_report.json)
└── metadata/        <-- Dynamic dataset registries (dataset_registry.json)
```

---

## 🚀 Step 1: Place Your Inputs

### 1. CCTV Video Feeds (`data/videos/`)
- Drop the video recordings inside `data/videos/`.
- Ensure files use standard MP4 or AVI containers encoded with H.264 / AVC video codecs.
- Filenames should match calibrated cameras: e.g., `CAM-MAIN-01.mp4`.

### 2. Store polygonal layouts (`data/layouts/`)
- Store layout definitions inside `data/layouts/store_layout.json`.
- Coordinates must declare boundary vertices for every zone, for example:
```json
{
  "zones": {
    "store_entrance": [[10, 380], [630, 380], [630, 470]],
    "makeup_zone": [[10, 10], [300, 10], [300, 180]]
  }
}
```

### 3. Cashier POS Ledgers (`data/pos/`)
- Save POS logs to `data/pos/pos_transactions.csv`.
- Schema must include: `transaction_id`, `store_id`, `timestamp` (ISO-8601 UTC format), and `amount_inr`.

---

## 🔍 Step 2: Validate the Dataset

Before running the computer vision stream loop, run the **oracle validator** to confirm formats, frame rates, poly closed shapes, and database constraints:

```bash
python scripts/validate_dataset.py
```

This updates the dataset registry (`data/metadata/dataset_registry.json`) and generates a structured reports ledger in `data/validation/dataset_report.json`.

---

## 📊 Step 3: Inspect Ingested Metadata

Print a clean human-readable dashboard summarizing active files sizes, zones, and transactional rows counts:

```bash
python scripts/inspect_dataset.py
```

---

## 🏥 Step 4: Run the Dataset Health Check

Retrieve a quick machine-interpretable health code (exit codes 0 for success, 2 for failures) to verify environment safety inside deployment scripts:

```bash
python scripts/dataset_healthcheck.py
```

---

## 🎥 Step 5: Boot the Stream Pipeline

Once validations return a `PASSED` status, launch the main processing orchestrator:

```bash
python pipeline/main.py
```

*Note: The pipeline automatically parses dataset validation reports before startup, preventing execution if files are corrupted or missing.*
