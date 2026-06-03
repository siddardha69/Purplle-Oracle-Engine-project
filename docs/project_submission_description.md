# Purplle Store Intelligence System (Oracle Engine) 🔮
## Project Submission Description & Technical Document

---

### 1. Problem Statement
Traditional brick-and-mortar retail operations operate in a state of statistical blindness compared to e-commerce storefronts. While digital stores track every click, scroll, hover, and drop-off to optimize the conversion funnel, physical stores remain limited to aggregate sales figures and basic daily footfall counters. 

The core problems addressed by this platform include:
- **Opaque Shopper Journeys**: Retail managers cannot trace how shoppers navigate the floor plan. They lack the visibility to know if a customer entered the makeup aisle, spent minutes at the skincare counter, or left out of frustration due to a long checkout queue.
- **Underutilized Security CCTV Infrastructure**: Passive camera feeds are treated strictly as historical recordings for theft investigations rather than real-time telemetry sources. 
- **Shopper Occlusion & Tracking Fragmentation**: Simple computer vision trackers fail in real-world retail layouts. Shoppers frequently walk behind shelves, bend down, or overlap with other customers, causing track segment dropouts. This results in single shopper journeys being fractured into multiple, disjointed session records.
- **The Physical-Digital Analytics Gap**: There is no automated, real-time mechanism to match a visitor's spatial journey (e.g., browsing lipstick counters for 3 minutes) with their corresponding checkout transaction at the Point-of-Sale (POS) terminal. This prevents retail brands from computing accurate aisle-level and store-level conversion rates.
- **Operational Blind Spots**: Inefficiencies such as checkout queue bottlenecks, lingering in restricted zones, or suspicious disappearances near high-value counters go undetected in real-time, resulting in lost sales and high shrinkage.

---

### 2. Proposed Solution
The **Purplle Store Intelligence System (Oracle Engine)** is a production-grade, edge-compatible spatial CCTV analytics and operational anomaly detection platform. It transforms standard security camera streams into real-time spatial telemetry, providing full funnel conversion evaluations.

The system operates through a unified, stateful pipeline:
1. **Edge Stream Ingestion**: Captures live CCTV video frames, processing them through a multi-threaded loader.
2. **Shopper Detection & Re-Identification**: Employs a fine-tuned **YOLOv8** model to isolate shopper bounding boxes, combined with feature extraction embeddings (Re-ID) to persist identities across camera frames.
3. **Stateful Occlusion Coprocessing**: Feeds tracked objects into the custom **Occlusion Intelligence Engine** which dynamically monitors visibility metrics, reasons about lost tracks, and evaluates blind spot risks.
4. **Spatial Polygon Routing**: Checks bottom-center shopper coordinates against custom polygonal floor zones (e.g., Makeup Zone, Skincare Zone, Fragrance Counter) using Shapely Point-in-Polygon (PIP) mathematics.
5. **Real-time Event Brokerage**: Transmits spatial transitions (e.g., zone entries, loitering dwells, exits) to a FastAPI backend. Events are cached in a Redis Sorted Set / Hash structure and saved in a relational database (PostgreSQL/SQLite).
6. **Digital POS Correlation**: Runs the `POSCorrelationService` to map visitor tracks to POS cash logs via time-decay proximity matrices.
7. **Premium Telemetry Control Center**: Renders a luxury dark-themed Streamlit dashboard showing footfall trends, live video overlays, spatial grids, Conversion Funnels, and scrolling WebSocket alerts without UI stuttering.

---

### 3. System Architecture & Technical Specifications

The system is designed around **Clean Architecture Boundaries**, ensuring complete decoupling between the machine learning computer vision loop, the REST/WebSocket API layer, the persistent database models, and the frontend visualization panel.

#### A. Block Diagram & Architectural Layers
- **Ingestion & Computer Vision Layer (`pipeline/`)**: Handles multi-threaded frame decoding, YOLOv8 inference, tracker coordinate smoothing, and Re-ID embedding matching.
- **Stateful Intelligence Coprocessor (`pipeline/occlusion_engine.py` & `pipeline/zones.py`)**: Runs Point-in-Polygon (PIP) checks, tracks zone dwell times, and computes shopper visibility and track-loss classifications.
- **High-Performance REST & Socket API (`app/`)**: Written in FastAPI. Manages client connections, tracks active session states, logs execution latencies, and routes endpoints.
- **High-Velocity Cache Layer (Redis)**: Manages low-latency occupancies, active session counts, queue sizes, and feeds websocket broadcasters.
- **Relational Data Layer (`app/models/` via SQLAlchemy)**: Automates table setup and stores telemetry logs in SQLite (for rapid developer booting) or PostgreSQL (for production clusters).
- **Luxury Telemetry Panel (`dashboard/`)**: Built on Streamlit, using a custom glassmorphic stylesheet and WebSocket listener threads.

```
                     +---------------------------------------+
                     |       CCTV Stream Ingest Pipeline     |
                     |  - VideoLoader Thread                 |
                     |  - YOLOv8 Detector & Tracker          |
                     |  - Re-ID Embedding Matching           |
                     +-------------------+-------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |    Occlusion & Zone Intelligence      |
                     |  - PolygonZone (Shapely PIP)          |
                     |  - OcclusionIntelligenceEngine        |
                     +-------------------+-------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |            FastAPI Backend            |
                     |  - REST Endpoints (/metrics, /funnel) |
                     |  - WebSockets Connection Broadcasters |
                     +---------+-------------------+---------+
                               |                   |
                               v                   v
                     +------------------+ +------------------+
                     |  Redis Ingest    | |  Relational DB   |
                     |  - Sorted Sets   | |  - PostgreSQL    |
                     |  - Active Hashes | |  - SQLite Fallback|
                     +------------------+ +------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |          Glassmorphic Dashboard       |
                     |  - Streamlit UI components            |
                     |  - Live Socket Listener Daemon        |
                     |  - st.fragment Zero-Flicker Renderer  |
                     +---------------------------------------+
```

#### B. Database Schema Specification
The relational schema maps out physical locations, camera sensors, visitor paths, events, analytics aggregates, transaction cash-box files, and anomalies.

1. **`stores`**:
   - `id` (String(36), PK): UUID of the physical outlet.
   - `name` (String(100)): Store name (e.g. DLF Mall of India).
   - `location` (String(200)): Retail location.
   - `layout` (JSON / JSONB): Custom polygon coordinate vectors outlining shopping aisles.
   - `created_at` (DateTime): Timestamp of creation.
2. **`cameras`**:
   - `id` (String(36), PK): UUID of the sensor.
   - `store_id` (String(36), FK to `stores.id`): Maps camera to its store location.
   - `name` (String(100)): Camera identifier (e.g., Aisle 2 Skincare).
   - `rtsp_url` (String(500)): CCTV RTSP feed link.
   - `calibration` (JSON / JSONB): Lens homography matrices mapping 2D camera pixels to 2D floor coordinates.
3. **`visitor_sessions`**:
   - `id` (String(36), PK): UUID of the unique shopper path.
   - `store_id` (String(36), FK to `stores.id`): Associated store.
   - `visitor_track_id` (String(100), Index): Tracker ID assigned by the CV pipeline.
   - `start_time` (DateTime): Timestamp of entry.
   - `end_time` (DateTime, Nullable): Timestamp of exit.
   - `dwell_time` (Float): Total store stay in seconds.
   - `converted` (Boolean): Confirms if journey matched a POS checkout receipt.
4. **`events`**:
   - `id` (String(36), PK): UUID of the transition log.
   - `session_id` (String(36), FK to `visitor_sessions.id`): Shopper path association.
   - `camera_id` (String(36), FK to `cameras.id`): Sensor recording the event.
   - `event_type` (String(50)): Transition action (`ENTER`, `EXIT`, `DWELL`).
   - `zone_name` (String(100)): Intersected layout aisle (e.g., `makeup_zone`).
   - `event_timestamp` (DateTime): Time of action.
   - `duration` (Float, Nullable): Dwell duration in the zone.
   - `event_metadata` (JSON / JSONB): Includes bounding box coordinates `[x1, y1, x2, y2]` and detection confidence scores.
5. **`zone_metrics`**:
   - `id` (Integer, PK): Auto-increment identifier.
   - `store_id` (String(36), FK to `stores.id`): Associated store.
   - `zone_name` (String(100)): Target aisle.
   - `timestamp` (DateTime): Hour of consolidation.
   - `total_footfall` (Integer): Total unique entries.
   - `avg_dwell_seconds` (Float): Average shopper stay in the aisle.
6. **`pos_transactions`**:
   - `id` (String(36), PK): Transaction record.
   - `store_id` (String(36), FK to `stores.id`): Sale branch.
   - `transaction_id` (String(100)): Physical terminal receipt number.
   - `timestamp` (DateTime): Transaction checkout time.
   - `amount` (Float): Bill value in INR (₹).
7. **`anomalies`**:
   - `id` (String(36), PK): UUID.
   - `store_id` (String(36), FK to `stores.id`): Associated store.
   - `session_id` (String(36), FK to `visitor_sessions.id`, Nullable): Associated shopper path.
   - `anomaly_type` (String(100), Index): E.g., `VISIBILITY_COLLAPSE`, `QUEUE_BOTTLENECK`, `LOITERING`, `HIGH_RISK_DISAPPEARANCE`.
   - `severity` (String(50)): Alert level (`INFO`, `WARNING`, `CRITICAL`).
   - `description` (String(500)): Explanatory telemetry message.
   - `detected_at` (DateTime): Alert trigger timestamp.
   - `metadata` (JSON / JSONB): Diagnostic context.

---

### 4. Key Features
- **Real-Time CCTV Multi-Object Tracking**: Ingests standard RTSP feeds, running YOLOv8 detection and custom Re-ID features to trace shopper bounding boxes across floor plan coordinates.
- **Polygon Zone Footfall & Dwell Trackers**: Employs Shapely geometry coordinates to define virtual gates and aisles. Computes zone entries, exits, and triggers loitering alerts (`ZONE_DWELL`) when shopper dwell times cross a configurable threshold (e.g. 30 seconds).
- **POS Transaction Correlation & Funnel Evaluation**: Correlates checkout exit times and billing zone dwell times (e.g., minimum 45s at checkout) against actual POS cash-terminal transactions using temporal-spatial proximity matching. It constructs a full-funnel drop-off visualization (Footfall -> Product Browsing -> Checkout Queue -> Confirmed Conversion).
- **Occlusion & Disappearance Intelligence**: Stateful coprocessor calculating visibility scores. It detects rapid visibility collapses (when shoppers are blocked by shelves) and determines if shopper disappearance is a normal exit or a potential security risk.
- **Spatial Density Hotspot Visualization**: Aggregates visitor coordinates to construct density hotspots, plotted onto layout scatter grids.
- **Operational Anomaly Alarms**: Automatically flags operations alerts such as checkout queue bottlenecks (e.g. >5 shoppers waiting), excessive loitering, and unexplained path losses. Alarms are written to SQL databases and broadcasted over WebSockets.
- **Premium Glassmorphic Control Dashboard**: Uses advanced CSS styling, custom dark aesthetics, multi-threaded WebSocket listeners, and Streamlit fragments to render real-time telemetry updates.

---

### 5. Innovation & Technical Distinction

The Purplle Store Intelligence System stands out due to its custom algorithmic contributions to physical spatial tracking:

#### A. Stateful Multi-Factor Visibility Model
Rather than relying solely on raw YOLOv8 detector confidence, the system calculates a dynamic **Shopper Visibility Score ($V_t \in [0, 100]$)** at frame $t$:

$$V_t = 100 \times \left( c_{det} w_1 + s_{area} w_2 + p_{frame} w_3 + c_{track} w_4 + k_{cont} w_5 \right)$$

Where:
1. **$c_{det}$ (Detection Confidence)**: Raw neural network probability score.
2. **$s_{area}$ (Bounding Box Stability)**: Measures area changes between frames. A rapid area change implies sudden overlaps:
   $$s_{area} = 1.0 - \min\left(\frac{|Area_t - Area_{t-1}|}{Area_{t-1}}, 1.0\right)$$
3. **$p_{frame}$ (Persistence)**: Normalizes tracking duration to filter short false-positive tracks.
4. **$c_{track}$ (Tracker State)**: Evaluates if tracker is statefully `"active"` or `"lost"`.
5. **$k_{cont}$ (Continuity)**: Ratio of frames detected to total elapsed frames in the pipeline.

#### B. Trajectory & Blind Spot Risk Model
When a shopper's track is lost, the **Occlusion Engine** computes an automated **Blind Spot Risk Model** rather than discarding the data:
- **Velocity Vector Estimation**: Calculates trajectory vectors $\vec{v} = (\Delta x, \Delta y)$ over historical frames.
- **Boundary Proximity (Exit Crossing Validation)**: Computes the minimum perpendicular distance $d$ to the configured entrance/exit boundary line segment.
  - If $d < \text{threshold}$ and tracking was stable: Risk is classified as **LOW** (normal store exit).
  - If $d > \text{threshold}$ and visibility collapsed in product zones: Risk is classified as **HIGH** (suspicious disappearance / severe occlusion).
  - If disappearance happens at billing: Risk is classified as **MEDIUM** (checkout queue occlusion).

#### C. Temporal-Spatial POS Matcher
The conversion system links offline footfall to actual sales logs. The correlation engine runs a matching sweeps pipeline matching session exit times $T_{exit}$ to POS terminal checkout times $T_{pos}$ with a time-decay curve:

$$\text{Probability} = \left( \left[1.0 - \frac{|T_{exit} - T_{pos}|}{300.0}\right] \times 0.70 \right) + \left( \min\left[\frac{\text{Dwell}_{checkout}}{45.0}, 1.0\right] \times 0.30 \right)$$

This formula scores potential transaction matches within a 5-minute (300s) window, using billing dwell time as a sanity check. It confirms conversions when the score exceeds $0.65$.

#### D. Zero-Flicker Dashboard Architecture
By combining background multi-threaded WebSocket listeners with Streamlit's `@st.fragment` decorator, the UI updates coordinates and alerts at a $1.0\text{s}$ interval. This allows the Streamlit UI to run without full-page reloads, preventing video feed stuttering or chart flickering.

---

### 6. Business Impact
- **Conversion Rate Optimization (CRO)**: Identifies conversion drop-offs between store zones (e.g. high footfall at makeup counter but low sales conversion) to help managers optimize pricing, signage, and product selection.
- **Aisle Layout & Merchandising Optimization**: Leverages spatial coordinate scatter grids and occupancy maps to test the performance of store layouts, shelf placements, and promotional displays.
- **Labor Optimization & Operational Excellence**: Alerts managers to checkout queue bottlenecks in real-time, allowing them to open registers during peak hours and minimize checkout abandonment.
- **Shrinkage & Loss Prevention**: High-risk shopper disappearance alerts notify security teams of suspicious events in high-value product areas.
- **Data-Driven Retail Decisions**: Integrates physical retail metrics with digital analytics, providing the detailed datasets needed to justify store expansion, staffing changes, and inventory investments.
