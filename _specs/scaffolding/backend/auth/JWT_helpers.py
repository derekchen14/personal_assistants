import jwt
import os
from typing import Dict, Optional, Union
from datetime import datetime, timedelta, timezone

from fastapi import Request, Response, HTTPException, Depends, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Load environment variables
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET_KEY environment variable is not set")

JWT_ALGORITHM = "HS256"
# Update default expiration to 7 days (604800 seconds)
JWT_EXP_DELTA_SECONDS = 604800
COOKIE_NAME = "auth_token"
# Set token refresh threshold to 1 day before expiration
REFRESH_THRESHOLD_SECONDS = 86400

def sign_JWT(payload: Dict) -> str:
    """
    Create a JWT token with the provided payload
    
    Args:
        payload: Dictionary containing data to encode in the token
        
    Returns:
        JWT token string
    """
    # Add expiration time to payload using timezone-aware datetime
    expiration = datetime.now(timezone.utc) + timedelta(seconds=JWT_EXP_DELTA_SECONDS)
    payload.update({"exp": expiration})
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_JWT(token: str) -> Dict:
    """
    Decode and verify a JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        jwt.PyJWTError: If token verification fails
    """
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

def set_jwt_cookie(response: Response, token: str) -> None:
    """
    Set JWT token as a secure HTTP-only cookie
    
    Args:
        response: FastAPI Response object
        token: JWT token string
    """
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,  # Only sent with HTTPS
        samesite="strict",  # Prevents CSRF
        max_age=JWT_EXP_DELTA_SECONDS,
        path="/"
    )

def clear_jwt_cookie(response: Response) -> None:
    """
    Clear the JWT cookie
    
    Args:
        response: FastAPI Response object
    """
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True
    )

def refresh_token_if_needed(auth_token: str, response: Response) -> bool:
    """
    Check if token needs refresh and set a new token cookie if needed
    
    Args:
        auth_token: Current JWT token
        response: FastAPI Response object to set refreshed cookie
    
    Returns:
        bool: True if token was refreshed, False otherwise
    """
    try:
        # Decode without verification first to avoid unnecessary crypto operations
        unverified_payload = jwt.decode(auth_token, options={"verify_signature": False})
        
        # Check if token will expire soon (within threshold)
        exp_timestamp = unverified_payload.get('exp', 0)
        current_timestamp = datetime.now(timezone.utc).timestamp()
        
        # If token expires soon, refresh it
        if exp_timestamp - current_timestamp < REFRESH_THRESHOLD_SECONDS:
            # Now verify the token properly before refreshing
            payload = decode_JWT(auth_token)
            # Create new token with the same payload but new expiration
            new_token = sign_JWT(payload)
            # Set the new token in cookie
            set_jwt_cookie(response, new_token)
            return True
            
    except:
        # If any error occurs during refresh, just continue
        pass
        
    return False

# Centralized function to extract JWT token from various sources
def get_token(request: Request = None, authorization: HTTPAuthorizationCredentials = None, 
              auth_token: Optional[str] = Cookie(None)) -> str:
    """
    Extract JWT token from cookie, authorization header, or query parameter
    
    Args:
        request: FastAPI Request object
        authorization: HTTPAuthorizationCredentials from Bearer token
        auth_token: Value from the auth_token cookie
        
    Returns:
        JWT token string
        
    Raises:
        HTTPException: If no valid token is found
    """
    # First try to get from cookie (preferred method)
    if auth_token:
        return auth_token
    
    # Then try to get from Authorization header
    if authorization:
        return authorization.credentials
    
    # Finally try to get from query parameters or request headers
    if request:
        # Try query parameters
        token = request.query_params.get("token")
        if token:
            return token
        
        # Try Authorization header directly
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header.replace("Bearer ", "")
    
    # No token found
    raise HTTPException(status_code=401, detail="No valid authentication token provided")

# JWT Bearer authentication dependency (backwards compatible)
class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)
    
    async def __call__(self, request: Request, auth_token: Optional[str] = Cookie(None)):
        # First try to get from cookie
        if auth_token:
            try:
                decode_JWT(auth_token)
                return auth_token
            except jwt.PyJWTError:
                raise HTTPException(status_code=401, detail="Invalid token or expired token")
                
        # Fallback to Authorization header
        try:
            credentials = await super(JWTBearer, self).__call__(request)
            token = credentials.credentials
            
            # Verify the token
            decode_JWT(token)
            return token
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid token or expired token")
        except HTTPException:
            # If no Authorization header, check query parameters
            token = request.query_params.get("token")
            if token:
                try:
                    decode_JWT(token)
                    return token
                except jwt.PyJWTError:
                    pass
            
            raise HTTPException(status_code=401, detail="Invalid authentication")

# Dependency to extract user info from token
def get_current_user(token: str = Depends(JWTBearer())) -> Dict:
    """
    Extract user information from JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        User information from token payload
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        payload = decode_JWT(token)
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token or expired token")
