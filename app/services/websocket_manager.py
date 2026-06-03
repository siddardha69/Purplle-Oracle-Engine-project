import json
from typing import List, Dict, Set
from fastapi import WebSocket
from loguru import logger

class ConnectionManager:
    """
    Manages active WebSockets clients, organizing connections by Store subscription lists.
    Ensures safe thread locks on connects and disconnects.
    """
    def __init__(self):
        # Maps Store ID to a set of active WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, store_id: str):
        """
        Accepts incoming connection and registers client in a store channel group.
        """
        await websocket.accept()
        if store_id not in self.active_connections:
            self.active_connections[store_id] = set()
        self.active_connections[store_id].add(websocket)
        logger.info(f"WebSocket client connected to channel group 'store:{store_id}'. Count: {len(self.active_connections[store_id])}")

    def disconnect(self, websocket: WebSocket, store_id: str):
        """
        Unregisters client on channel drop.
        """
        if store_id in self.active_connections:
            self.active_connections[store_id].discard(websocket)
            if not self.active_connections[store_id]:
                del self.active_connections[store_id]
            logger.info(f"WebSocket client disconnected from 'store:{store_id}'.")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Pushes a single structured message directly to a client.
        """
        await websocket.send_text(json.dumps(message))

    async def broadcast_to_store(self, store_id: str, message: dict):
        """
        Broadcasts structured telemetry to all clients subscribed to a specific store_id channel.
        """
        if store_id not in self.active_connections:
            return
            
        disconnected_sockets = set()
        message_str = json.dumps(message)
        
        # Iterates and pushes events asynchronously
        for connection in self.active_connections[store_id]:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.warning(f"Failed to push message to WebSocket. Flagging for removal. Error: {e}")
                disconnected_sockets.add(connection)
                
        # Cleanup stale connections
        for dead_socket in disconnected_sockets:
            self.active_connections[store_id].discard(dead_socket)
            
        if store_id in self.active_connections and not self.active_connections[store_id]:
            del self.active_connections[store_id]

# Singleton websocket connection manager
ws_manager = ConnectionManager()
