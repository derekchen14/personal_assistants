import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from backend.middleware.auth_middleware import TokenRefreshMiddleware
from backend.middleware.activity_middleware import ActivityTrackingMiddleware
from backend.middleware.stripe_service import stripe_router

# Import routers from service modules
from backend.routers.table_service import table_router
from backend.routers.chat_service import chat_router
from backend.routers.utility_service import utility_router
from backend.routers.user_service import user_router
from backend.routers.sheet_service import sheet_router
from backend.routers.interaction_service import interaction_router
from backend.routers.auth_service import auth_router
from backend.routers.external_source_service import external_source_router
from backend.routers.conversation_service import conversation_router

# Temporary fix for multiprocessing
from backend.manager import Manager, default_args

global_manager = Manager()

def get_agent_with_token(token, args=default_args):
    """Simplified version that uses the global manager directly"""
    return global_manager.get_agent_with_token(token, args)

def reset_agent_with_token(token, args=default_args):
    """Simplified version that uses the global manager directly"""
    return global_manager.reset_agent(token, args)

def cleanup_agent_by_token(token, source='general'):
    """Simplified version that uses the global manager directly"""
    return global_manager.cleanup_by_token(token, source)

def register_cleanup_callback(callback):
    """Simplified version that uses the global manager directly"""
    global_manager.register_cleanup_callback(callback)

def update_last_activity(user_id):
    """Simplified version that uses the global manager directly"""
    global_manager.update_last_activity(user_id)

# Monkey patch all the manager functions
import backend.manager
backend.manager.get_agent_with_token = get_agent_with_token
backend.manager.reset_agent_with_token = reset_agent_with_token
backend.manager.cleanup_agent_by_token = cleanup_agent_by_token
backend.manager.register_cleanup_callback = register_cleanup_callback
backend.manager.update_last_activity = update_last_activity

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(TokenRefreshMiddleware)
app.add_middleware(ActivityTrackingMiddleware)
# Set up CORS middleware
app.add_middleware(
  CORSMiddleware,
  allow_origins=[
    'http://localhost:1414',
    'https://www.soleda.app',
    'https://soleda.ai',
    'http://localhost:8000',
    'http://localhost:5173',
    ],  # ['*'],
  allow_credentials=True,
  allow_methods=['*'],
  allow_headers=['*'],
)

# Load environment variables
load_dotenv()

# Include all service routers under the main app with the appropriate prefixes
app.include_router(utility_router, prefix='/api/v1')
app.include_router(user_router, prefix='/api/v1')
app.include_router(sheet_router, prefix='/api/v1')
app.include_router(interaction_router, prefix='/api/v1')
app.include_router(auth_router, prefix='/api/v1')
app.include_router(external_source_router, prefix='/api/v1')
app.include_router(chat_router, prefix='/api/v1')
app.include_router(stripe_router)
app.include_router(table_router)
app.include_router(conversation_router, prefix='/api/v1')
