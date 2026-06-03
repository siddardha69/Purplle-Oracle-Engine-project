from fastapi import APIRouter
from app.api.v1 import health, events, metrics, funnels, heatmaps, anomalies, stream

api_router = APIRouter()

# Register sub-modules under standard V1 path names
api_router.include_router(health.router, tags=["System Health"])
api_router.include_router(events.router, tags=["Movement Events"])
api_router.include_router(metrics.router, tags=["Analytical Metrics"])
api_router.include_router(funnels.router, tags=["Conversion Funnels"])
api_router.include_router(heatmaps.router, tags=["Spatial Heatmaps"])
api_router.include_router(anomalies.router, tags=["Security & Operational Anomalies"])
api_router.include_router(stream.router, tags=["Live Ingestion Streams"])

