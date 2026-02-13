import os


from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.auth.JWT_helpers import sign_JWT, decode_JWT, set_jwt_cookie, clear_jwt_cookie, JWTBearer
from backend.auth.user_fields import UserFields, UserLoginFields
from backend.db import get_db
from database.tables import User
from backend.manager import cleanup_agent_by_token

from slowapi import Limiter
from slowapi.util import get_remote_address

# Reuse the limiter from the main application
limiter = Limiter(key_func=get_remote_address)
user_router = APIRouter()

@user_router.get('/users')
def get_users(db=Depends(get_db)):
  users = db.query(User).all()
  return users

@user_router.post('/user/signup', tags=['user'])
@limiter.limit("5/minute")  # Limit to 5 signup attempts per minute per IP
def create_user(request: Request, user: UserFields, response: Response, db=Depends(get_db)):
  if db.query(User).filter(User.email == user.email).first():
    raise HTTPException(status_code=400, detail='Email already exists')
  user_item = User(
      first=user.first,
      last=user.last,
      email=user.email,
  )
  user_item.set_password(user.password)
  db.add(user_item)
  db.commit()
  db.refresh(user_item)
  
  # Include user ID in the JWT payload
  payload = {
    'email': user_item.email,
    'userID': user_item.id
  }
  token = sign_JWT(payload)
  
  # Set the JWT as a secure HTTP-only cookie
  set_jwt_cookie(response, token)
  
  # Return successful response with user info (but not the token directly)
  return {
    'success': True,
    'user': {
      'userID': user_item.id,
      'email': user_item.email,
      'first': user_item.first,
      'last': user_item.last
    }
  }

@user_router.post('/user/login', tags=['user'])
@limiter.limit("5/minute")  # Limit to 5 login attempts per minute per IP
def user_login(request: Request, response: Response, user: UserLoginFields = Body(...), db=Depends(get_db)):
  user_from_db = db.query(User).filter(User.email == user.email).first()
  if user_from_db and user_from_db.check_password(user.password):
    user_email = user_from_db.email
    # Include user ID in the JWT payload
    payload = {
      'email': user_email,
      'userID': user_from_db.id
    }
    jwt_token = sign_JWT(payload)
    
    # Set the JWT as a secure HTTP-only cookie
    set_jwt_cookie(response, jwt_token)
    
    # Return user info without exposing the token
    return {
      'success': True,
      'user': {
        'userID': user_from_db.id,
        'email': user_from_db.email,
        'first': user_from_db.first,
        'last': user_from_db.last
      }
    }
  
  if user_from_db is None:
    return JSONResponse(status_code=400, content={'error': 'User not found'})
  return JSONResponse(status_code=400, content={'error': "Wrong login details!"})

@user_router.post('/user/logout', tags=['user'])
def user_logout(response: Response, token: str = Depends(JWTBearer())):
  # Clean up the agent before clearing the JWT cookie
  if token:
    cleanup_agent_by_token(token, 'logout')
    
  # Clear the JWT cookie
  clear_jwt_cookie(response)
  return {'message': "Logged out successfully!"}

@user_router.post('/user/reset')
def reset_conversation(request: Request, token: str = Depends(JWTBearer())):
  # Let manager handle the agent reset with token
  from backend.routers.chat_service import reset_agent_chat
  
  # Extract email from token for the message response
  payload = decode_JWT(token)
  user_email = payload.get('email')
  
  return reset_agent_chat(user_email, token)