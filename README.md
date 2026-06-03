---
title: Purplle Store Intelligence
emoji: 🔮
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
---

# Purplle Store Intelligence System (Oracle Engine) 🔮

Production-grade edge CCTV spatial analytics, purchase funnel evaluation, and operational anomaly detection platform built for the **Purplle Tech Challenge 2026**.

---

## 🚀 Highlights & Features

- **Clean Architecture Boundary**: Segregated modules across machine learning engines (`pipeline/`), REST and websocket streams (`app/`), and telemetry visual dashboards (`dashboard/`).
- **Pydantic V2 Settings Manager**: Advanced configuration settings validations supporting runtime fallback overrides.
- **Loguru Structured Telemetry**: High-fidelity logs serialization mapping crucial context (`trace_id`, `store_id`, `camera_id`, `latency`, `status_code`) natively into stdout streams and rotation ZIP files.
- **Redis Multi-Aisle Ingestion Broker**: Fast occupy sorted sets and occupancy hashes supporting low-latency REST calls and WebSocket connection managers.
- **SQLite Fallback**: Zero-configuration local developer bootup out of the box using dynamic SQL engine switching.
- **Premium Glassmorphic Streamlit Dashboard**: Ultra-premium Deep Purple brand portal containing footfall trends, conversion funnels, spatial grids, active warnings lists, and WebSockets scrolling activity feed.

---

## 📂 Code Layout

```
store-intelligence/
├── configs/            # Settings parser and loguru serializations
├── app/                # FastAPI framework (SQLAlchemy models, Routers, WS managers)
├── pipeline/           # OpenCV edge frames loops (YOLOv8 & Centroid tracking)
├── dashboard/          # Streamlit UI charts and websocket subscriber threads
├── tests/              # Pytest checks (In-memory SQLite isolation fixtures)
├── data/               # Persistent media folders, store layout JSON, transaction CSVs
├── scripts/            # Database seed and pipeline traffic emulators
└── docker/             # Production Dockerfiles (Optimized OpenCV system libraries layers)
```

---

## 🛠️ Step-by-Step Developer Boot

### 1. Simple Virtual Environment Setup (Recommended)
You can set up the entire environment locally without Docker in under 1 minute:

```bash
# Setup virtual environment and download dependencies
make setup

# Activate environment (Windows PowerShell)
.venv/Scripts/activate
```

### 2. Synchronize Schemas & Seed database Mocks
This populates SQLite/PostgreSQL with mock cameras, active stores, shopper traces, zone metrics, and alerts:
```bash
make seed
```

### 3. Launch Services (REST + WebSockets API & UI Dashboard)
Open two separate terminal frames to launch the FastAPI server and the Streamlit dashboard:

*Terminal 1 (REST API):*
```bash
make run
```
*Terminal 2 (Streamlit UI Dashboard):*
```bash
make run-dashboard
```
*Access URLs:*
- **Swagger Docs Portal**: `http://localhost:8000/docs`
- **Analytics Visual UI Panel**: `http://localhost:8501`

### 4. Animate the Dashboard (Edge Stream Emulator)
To see charts, conversion metrics, heatmaps, and a websocket event ticket update in real-time, execute the simulator stream:
```bash
make stream-mock
```

---

## 🐳 Dockerized Multi-Container Orchestration

To compile and launch the production-ready infrastructure (PostgreSQL database cluster, Redis caching layer, FastAPI backend engine, and Streamlit telemetry dashboard):

```bash
# Compile and boot all composed services in background
make docker-up

# Tear down container clusters and persistent scopes
make docker-down
```

---

## 📊 Database Schema Summary

The relational database layer utilizes six optimized PostgreSQL tables:
1. **`stores`**: Tracks storefront dimensions and maps zone vertices matrices (`JSONB`).
2. **`cameras`**: Catalog maps RTSP edge endpoints to stores and stores calibration matrices (`JSONB`).
3. **`visitor_sessions`**: Groups visitor movement histories and correlates purchase conversions against POS transaction files.
4. **`events`**: High-frequency movement events captured by the vision pipeline (`ENTER` / `EXIT`).
5. **`zone_metrics`**: Hour-by-hour footprint consolidations ensuring fast dashboard performance.
6. **`anomalies`**: Operational security alarm triggers (Lingering, checkout queue bottlenecks).

---

## 🧪 Testing & Code Quality Assurance

We use isolated in-memory SQLite instances to run fast unit and integration checks:

```bash
# Execute Pytest test suits
make test

# Verify structural lints
make lint

# Run Black and Isort formatters
make format
```
