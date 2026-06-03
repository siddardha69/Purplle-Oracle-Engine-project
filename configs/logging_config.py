import json
import sys
from loguru import logger
from configs.settings import settings

def serialize_log(record):
    """
    Serializes a log record to structured JSON format.
    Extracts custom bind parameters such as trace_id, store_id, camera_id, latency, event_count, status_code.
    """
    payload = {
        "timestamp": record["date"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "logger": record["name"],
        "file": record["file"].name,
        "line": record["line"],
        "function": record["function"],
    }
    
    # Extract contextual dynamic fields from extra
    extra = record["extra"]
    context_keys = ["trace_id", "store_id", "camera_id", "latency", "event_count", "status_code"]
    
    for key in context_keys:
        if key in extra:
            payload[key] = extra[key]
            
    # Include all other extra keys if present
    other_extras = {k: v for k, v in extra.items() if k not in context_keys}
    if other_extras:
        payload["extra"] = other_extras
        
    return json.dumps(payload)

def json_formatter(record):
    """
    Loguru formatter callback adding a serialized representation directly to record["extra"].
    """
    record["extra"]["serialized"] = serialize_log(record)
    return "{extra[serialized]}\n"

def configure_logging():
    """
    Configures Loguru logging systems.
    Binds development styles (colorful, verbose) or production engines (structured JSON stream).
    """
    # Remove standard system handlers
    logger.remove()
    
    # Establish log level from configuration
    log_level = settings.LOG_LEVEL
    
    # Configure console logging
    if settings.ENVIRONMENT == "production":
        # Production Console: Output clean JSON to stdout
        logger.add(
            sys.stdout,
            level=log_level,
            format=json_formatter,
            backtrace=False,
            diagnose=False
        )
    else:
        # Development Console: Beautiful, colorful, legible terminal telemetry
        dev_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level> "
            "<light-black>{extra}</light-black>"
        )
        logger.add(
            sys.stdout,
            level=log_level,
            format=dev_format,
            colorize=True,
            backtrace=True,
            diagnose=True
        )
        
    # Configure file logging if enabled
    if settings.LOG_TO_FILE:
        if settings.ENVIRONMENT == "production":
            logger.add(
                settings.LOG_FILE_PATH,
                level=log_level,
                format=json_formatter,
                rotation="50 MB",
                retention="10 days",
                compression="zip"
            )
        else:
            logger.add(
                settings.LOG_FILE_PATH,
                level=log_level,
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message} {extra}",
                rotation="10 MB",
                retention="3 days"
            )
            
    # Bind initial default context to avoid KeyError
    logger.configure(extra={
        "trace_id": "SYS-INIT",
        "store_id": "GLOBAL",
        "camera_id": "GLOBAL",
        "latency": 0.0,
        "event_count": 0,
        "status_code": 0
    })
    
    logger.info(f"Logging initialized. Level: {log_level}, Environment: {settings.ENVIRONMENT}")

# Execute setup immediately
configure_logging()
