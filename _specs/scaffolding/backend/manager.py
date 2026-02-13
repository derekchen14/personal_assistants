import os
import sys
import time
import traceback
import gc
import threading
from argparse import Namespace
from typing import  Optional, List, Callable
import asyncio

from fastapi import HTTPException
import jwt

from backend.agent import Agent
from backend.db import get_db
from backend.auth.JWT_helpers import decode_JWT, get_token
from dotenv import load_dotenv

load_dotenv()

DEBUG = os.getenv("CRASH_ON_EXCEPTION", True)
# Default ML parameters
default_args = Namespace(
  api_version="claude-sonnet-4-0",
  allow_dev_mode=True,
  temperature=0.2,
  threshold=0.6,
  drop_rate=0.1,
  max_length=512,
  level='medium',
  verbose=True,
  debug=DEBUG
)

class ProtectedDict:
  def __init__(self):
    self._data = {}

  def __get__(self, instance, owner):
    # Only allow access from methods of the owning class
    frame = sys._getframe(1)
    if frame.f_code.co_name in owner.__dict__:
      return self._data
    raise AttributeError("Access to protected attribute denied")

  def __set__(self, instance, value):
    self._data = value

class Manager:
  """
  Manages the creation, access, and cleanup of Agent instances.
  Provides secure access to agents with JWT verification.
  """
  _agents = ProtectedDict()
  _last_activity = ProtectedDict()
  _cleanup_callback = None
  _write_lock = threading.Lock()  # Lock only for write operations

  def __init__(self):
    self._agents = {}
    self._last_activity = {}
  
  def get_agent_with_token(self, token: str, args: Namespace = default_args) -> Agent:
    """
    Get or create an Agent instance with JWT verification.
    
    Args:
        token: JWT token containing user authentication info
        args: Agent configuration parameters
        
    Returns:
        Agent instance for the authenticated user
        
    Raises:
        HTTPException: If token is invalid or unauthorized
    """
    try:
      # Verify and decode JWT token
      payload = decode_JWT(token)
      
      user_email = payload.get('email')
      user_id = payload.get('userID')
      
      if not user_email or not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
      
      # Update last activity timestamp
      self._last_activity[user_id] = time.time()
      
      # Return existing agent or create new one
      if user_id in self._agents:
        return self._agents[user_id]
      
      # If agent doesn't exist, acquire write lock to create it
      with self._write_lock:
        # Double check after acquiring write lock
        if user_id in self._agents:
          return self._agents[user_id] 
        agent = self._create_agent(user_id, args)
        if agent:
          self._agents[user_id] = agent
          return agent
        else:
          raise HTTPException(status_code=500, detail="Failed to create agent")
          
    except jwt.PyJWTError as ecp:
      print(f"JWT verification failed: {ecp}")
      raise HTTPException(status_code=401, detail="Invalid authentication token")
  
  def _create_agent(self, user_id: int, args: Namespace = default_args) -> Optional[Agent]:
    """
    Create a new Agent instance for a user.
    
    Args:
        user_id: Database user ID
        args: Agent configuration parameters
        
    Returns:
        New Agent instance or None if creation failed
    """
    try:
        # Enable verbose logs for specific users (e.g., for testing)
        if user_id == 2:  # Test user ID
            args.verbose = True
            args.allow_dev_mode = True
            
        # Ensure database connection is available
        get_db()
        # Create agent
        agent = Agent(user_id, args)
        return agent
        
    except Exception as e:
        print(f"Manager agent creation failed: {e}")
        return None
  
  # Register a callback function to be called when an agent is cleaned up
  def register_cleanup_callback(self, callback: Callable[[str], None]):
    self._cleanup_callback = callback
  
  def cleanup_agent(self, user_id: str, source: str = 'general') -> bool:
    """
    Clean up an agent instance and its associated data.
    
    Args:
        user_id: The user ID associated with the agent
        source: The source of the cleanup request (for logging)
        
    Returns:
        bool: True if cleanup was successful, False otherwise
    """
    if user_id in self._agents:
      agent = self._agents[user_id]
      if agent is None:
        return False
      
      # Close the DuckDB connection - this is the most important part
      if hasattr(agent, 'memory') and agent.memory and hasattr(agent.memory, 'db_connection'):
        agent.memory.db_connection.close()
          
      # Remove agent from dictionaries
      del self._agents[user_id]
      if user_id in self._last_activity:
        del self._last_activity[user_id]
      
      # Force garbage collection to reclaim memory
      gc.collect()
      
      # Call the registered callback function if available
      if self._cleanup_callback:
        try:
          self._cleanup_callback(user_id)
        except Exception as callback_error:
          print(f"Error in cleanup callback: {callback_error}")
          pass
        return True
    return False
  
  def cleanup_by_token(self, token: str, source: str = 'general') -> bool:
    """
    Clean up an agent instance using the JWT token.
    
    Args:
        token: JWT token containing user authentication info
        source: The source of the cleanup request (for logging)
        
    Returns:
        bool: True if cleanup was successful, False otherwise
    """
    try:
      # Extract user ID from token
      payload = decode_JWT(token)
      user_id = payload.get('userID')
        
      if user_id:
        return self.cleanup_agent(user_id, source)
      return False
    except Exception as ecp:
      print(f"Error cleaning up agent by token: {ecp}")
      return False
      
  def reset_agent(self, token: str, args: Namespace = default_args) -> Agent:
    """
    Reset an existing Agent instance with JWT verification.
    
    Args:
        token: JWT token containing user authentication info
        args: Agent configuration parameters
        
    Returns:
        Reset Agent instance
        
    Raises:
        HTTPException: If token is invalid or agent doesn't exist
    """
    try:
      # Verify and decode JWT token
      payload = decode_JWT(token)
      
      user_id = payload.get('userID')
      
      if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
          
      # Check if agent exists
      if user_id not in self._agents:
        return None
          
      # Reset the agent
      agent = self._agents[user_id]
      agent.initialize_session(args)
      # Update activity timestamp
      self._last_activity[user_id] = time.time()

      return agent
        
    except jwt.PyJWTError as e:
      raise HTTPException(status_code=401, detail="Invalid authentication token")
    except Exception as ecp:
      print(f"Error resetting agent: {ecp}")
      raise HTTPException(status_code=500, detail="Internal server error")

  def update_last_activity(self, user_id: str):
    if user_id:
      self._last_activity[user_id] = time.time()

# Global instance of the Manager
manager = Manager()


# Helper functions to make usage simpler
def get_agent_with_token(token: str, args: Namespace = default_args) -> Agent:
  """Helper function to get an agent with token verification"""
  return manager.get_agent_with_token(token, args)


def reset_agent_with_token(token: str, args: Namespace = default_args) -> Agent:
  """Helper function to reset an agent with token verification"""
  return manager.reset_agent(token, args)

def get_user_id_from_token(token: str):
  """Extract user_id from JWT token"""
  payload = decode_JWT(token)
  user_id = payload.get('userID')
  if not user_id:
    # If userID is not in token, try to get email
    email = payload.get('email')
    if not email:
      raise HTTPException(status_code=401, detail='Invalid token: missing user identification')
    return email  # Use email as identifier if userID not present
  return user_id

def cleanup_agent_by_token(token: str, source: str = 'general') -> bool:
  """Helper function to clean up an agent with token verification"""
  return manager.cleanup_by_token(token, source)

# Helper function to register cleanup callback
def register_cleanup_callback(callback: Callable[[str], None]):
  """Register a callback function for agent cleanup notifications"""
  manager.register_cleanup_callback(callback)

def update_last_activity(user_id: str):
  """Helper function to update the last activity timestamp for a user"""
  manager.update_last_activity(user_id)