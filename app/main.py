import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from configs.settings import settings
import configs.logging_config  # Triggers logger initialization
from app.core.database import Base, engine
from app.core.redis import redis_manager
from app.api.v1.router import api_router
from app.api.websockets import router as websockets_router
from loguru import logger
import uuid

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Asynchronous lifespan manager handling application setup and tear-down blocks:
    - Auto-generates database schemas (extremely helpful for rapid bootstrapping).
    - Checks database engine connectivity.
    - Connects to high-performance Redis cache.
    """
    logger.info("Initializing Store Intelligence API startup sequences...")
    
    # 1. Automate database table creations (SQLite/Postgres initial sync)
    try:
        logger.info("Auto-generating database tables using SQLAlchemy declarative base...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database schemas generated/synchronized successfully.")
    except Exception as e:
        logger.error(f"Failed to synchronize database schemas on startup. Error: {e}")
        
    # 2. Establish Redis connections
    redis_manager.connect()
    
    yield
    
    # Tear-down logic on shutdown
    logger.info("Triggering API system shutdown sequence...")
    # Close Redis client if applicable
    redis_client = redis_manager.get_client()
    if hasattr(redis_client, "close"):
        redis_client.close()
        logger.info("Redis connections closed cleanly.")

# Instantiate main application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-grade spatial CCTV analytics backend for retail intelligence tracking.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration to allow local dashboards (e.g. Streamlit on port 8501) to interact seamlessly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_process_time_and_logging_middleware(request: Request, call_next):
    """
    Intercepts incoming requests to trace duration, request IDs, and status codes.
    Outputs structured Loguru trace lines.
    """
    start_time = time.perf_counter()
    trace_id = request.headers.get("X-Request-ID", f"TRC-{uuid.uuid4().hex[:6].upper()}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate execution latency
    process_time_ms = (time.perf_counter() - start_time) * 1000
    
    # Inject request details into Loguru binds
    logger.bind(
        trace_id=trace_id,
        store_id="GLOBAL",
        camera_id="GLOBAL",
        latency=round(process_time_ms, 2),
        event_count=0,
        status_code=response.status_code
    ).info(f"HTTP {request.method} {request.url.path} responded with status: {response.status_code}")
    
    # Add response trace header
    response.headers["X-Process-Time-Ms"] = str(round(process_time_ms, 2))
    response.headers["X-Request-ID"] = trace_id
    
    return response

# Mount master route blocks
app.include_router(api_router, prefix="/api/v1")
app.include_router(websockets_router)

@app.get("/", tags=["Root"])
def root_endpoint():
    """
    Root landing redirect to API descriptions.
    """
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "swagger_docs": "/docs"
    }
