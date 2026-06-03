from app.api.v1.router import api_router
from app.api.websockets import router as websockets_router

__all__ = ["api_router", "websockets_router"]
