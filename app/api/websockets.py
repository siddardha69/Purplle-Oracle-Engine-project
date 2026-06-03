import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.websocket_manager import ws_manager
from app.core.redis import get_redis
from loguru import logger

router = APIRouter()

# Keep track of active Redis pubsub listener tasks per store
active_pubsub_tasks = {}

async def redis_pubsub_listener(store_id: str):
    """
    Subscribes to a Redis Pub/Sub channel for a given store, listening for live CCTV events 
    and broadcasting them to active websocket clients.
    """
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    channel_name = f"store:{store_id}:live_events"
    
    logger.info(f"Starting Redis Pub/Sub listener on channel: {channel_name}")
    pubsub.subscribe(channel_name)
    
    try:
        # Loop forever looking for messages
        while True:
            # Check for messages (non-blocking sleep to play nice with asyncio event loops)
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                data_str = message["data"]
                try:
                    data_json = json.loads(data_str)
                    # Broadcast to all websocket connections active for this store_id
                    await ws_manager.broadcast_to_store(store_id, data_json)
                except Exception as ex:
                    logger.error(f"Error parsing Redis Pub/Sub event: {ex}")
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        logger.info(f"Redis Pub/Sub listener for store:{store_id} has been cancelled.")
    except Exception as e:
        logger.error(f"Error in Redis Pub/Sub listener loop: {e}")
    finally:
        pubsub.unsubscribe(channel_name)
        pubsub.close()

@router.websocket("/ws/store/{store_id}")
async def websocket_endpoint(websocket: WebSocket, store_id: str):
    """
    Handles live WebSocket pipelines for dashboards.
    Registers client connection, starts background Redis pubsub listener if needed, 
    and handles graceful connection drops.
    """
    await ws_manager.connect(websocket, store_id)
    
    # Spawn Redis pub/sub listener background task if not already running for this store
    if store_id not in active_pubsub_tasks or active_pubsub_tasks[store_id].done():
        task = asyncio.create_task(redis_pubsub_listener(store_id))
        active_pubsub_tasks[store_id] = task
        logger.info(f"Spawned background pubsub task for store: {store_id}")
        
    try:
        # Keep connection open. We can handle inbound socket messages here if needed.
        while True:
            data = await websocket.receive_text()
            # Just echoes back or logs the client keep-alive pings
            logger.debug(f"Received client socket data: {data}")
            await ws_manager.send_personal_message({"type": "PONG", "message": "alive"}, websocket)
            
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, store_id)
        
        # If there are no more active connections for this store, cancel the pub/sub listener task
        if store_id not in ws_manager.active_connections:
            if store_id in active_pubsub_tasks:
                active_pubsub_tasks[store_id].cancel()
                del active_pubsub_tasks[store_id]
                logger.info(f"Stopped background pubsub task for store: {store_id} since no clients remain.")
                
    except Exception as e:
        logger.error(f"WebSocket execution error on session: {e}")
        ws_manager.disconnect(websocket, store_id)
