from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.auth.JWT_helpers import refresh_token_if_needed

class TokenRefreshMiddleware(BaseHTTPMiddleware):
  """
  Middleware to automatically refresh JWT tokens for all API endpoints
  before they expire.
  """
  def __init__(self, app: ASGIApp):
    super().__init__(app)
    
  async def dispatch(self, request: Request, call_next):
    # Process the request and get the response
    response = await call_next(request)
    
    # Only attempt token refresh for API endpoints
    if request.url.path.startswith('/api'):
      # Get the token from cookie
      auth_token = request.cookies.get("auth_token")
      
      # If token exists, check if it needs refreshing
      if auth_token:
        refresh_token_if_needed(auth_token, response)
        
    return response