import time
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.auth.JWT_helpers import decode_JWT
from backend.manager import update_last_activity

class ActivityTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track user activity by updating the last_activity timestamp
    in the Manager for any authenticated request.
    """
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        
    async def dispatch(self, request: Request, call_next):
        try:
            auth_token = request.cookies.get("auth_token")
            
            if auth_token:
                payload = decode_JWT(auth_token)
                user_id = payload.get('userID')
                
                if user_id:
                    update_last_activity(user_id)
        except Exception:
            pass
            
        response = await call_next(request)
        return response 