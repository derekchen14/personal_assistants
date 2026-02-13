import os
import traceback
import json
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Security, Body, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.auth.JWT_helpers import JWTBearer, decode_JWT, get_token
from backend.db import get_db
from database.tables import Credential
from backend.utilities.oauth_setup import (create_oauth_url, create_resource_request, create_token_request, get_client_credentials)
from backend.utilities.oauth_config import PROVIDER_CONFIG
from backend.manager import get_agent_with_token, get_user_id_from_token

auth_router = APIRouter()

# Token encryption configuration
ENCRYPTION_KEY = os.getenv('OAUTH_ENCRYPTION_KEY')
ENCRYPTION_SALT = os.getenv('OAUTH_ENCRYPTION_SALT')

if not ENCRYPTION_KEY:
    raise ValueError("ENCRYPTION_KEY environment variable must be set")

def get_encryption_key(key=ENCRYPTION_KEY, salt=ENCRYPTION_SALT):
    """Derive a Fernet key from the provided key and salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt if isinstance(salt, bytes) else salt.encode(),
        iterations=100000,
    )
    key_bytes = key.encode() if isinstance(key, str) else key
    key = base64.urlsafe_b64encode(kdf.derive(key_bytes))
    return Fernet(key)

def encrypt_token(token):
    """Encrypt a token string."""
    if not token:
        return None
    f = get_encryption_key()
    token_bytes = token.encode()
    encrypted_token = f.encrypt(token_bytes)
    return encrypted_token.decode()

def decrypt_token(encrypted_token):
    """Decrypt a token string."""
    if not encrypted_token:
        return None
    f = get_encryption_key()
    encrypted_bytes = encrypted_token.encode()
    decrypted_token = f.decrypt(encrypted_bytes)
    return decrypted_token.decode()

async def get_provider_user_info(client: httpx.AsyncClient, data_source: str, access_token: str) -> Dict:
  """Fetch user info from provider using config-driven URL."""
  config = PROVIDER_CONFIG[data_source]
  headers = {'Authorization': f'Bearer {access_token}'}
  user_info_url = config['user_info_url']

  if '{access_token}' in user_info_url:
    user_info_url = user_info_url.format(access_token=access_token)

  response = await client.get(user_info_url, headers=headers)
  if response.status_code != 200:
    raise HTTPException(status_code=response.status_code, detail="Failed to fetch user info")
  return response.json()

def create_oauth_response(message: str, source: str, success: bool = True) -> HTMLResponse:
    msg_type = 'oauth_success' if success else 'oauth_error'
    return HTMLResponse(content=f"""
        <script>
          window.opener.postMessage({{ type: '{msg_type}', source: '{source}-callback' }}, '*');
          window.close();
        </script>
        <p>{message}</p>
    """)

@auth_router.get('/oauth/integration')
async def integration(data_source, token: str = Depends(JWTBearer()), db=Depends(get_db)):
  if token:
    user_id = get_user_id_from_token(token)
  else:
    raise HTTPException(status_code=400, detail="Invalid token")

  url = create_oauth_url(data_source)
  url += f"&state={data_source}"
  return RedirectResponse(url, status_code=302)

@auth_router.get('/oauth/callback')
async def callback(code: str = Query(None), error: str = Query(None), state: str = Query(None), db=Depends(get_db)):
    if error:
        return create_oauth_response("Authentication failed. You can close this window.", source='oauth', success=False)

    try:
      data_source, user_id = state.split('.')
      if data_source not in PROVIDER_CONFIG:
        raise HTTPException(status_code=400, detail=f"Invalid data source: {data_source}")
      user_id = int(user_id)

      url, payload, headers = create_token_request(data_source, code)

      async with httpx.AsyncClient() as client:
        response = await client.post(url, data=payload, headers=headers)
        if response.status_code != 200:
          raise HTTPException(status_code=response.status_code, detail=response.text)

        token_data = response.json()
        if 'expires_in' not in token_data:
          token_data['expires_in'] = 7200

        user_info = await get_provider_user_info(client, data_source, token_data["access_token"])
        vendor_id = user_info.get(PROVIDER_CONFIG[data_source]["id_field"])

        cred = Credential(
          user_id=user_id,
          vendor=data_source,
          vendor_id=vendor_id,
          access_token=encrypt_token(token_data['access_token']),
          refresh_token=encrypt_token(token_data.get('refresh_token')),
          token_expiry=datetime.utcnow() + timedelta(seconds=token_data['expires_in']),
          scope=PROVIDER_CONFIG[data_source]["scopes"],
          status='active',
          instance_url=token_data.get('instance_url')
        )
        db.add(cred)
        db.commit()

        return create_oauth_response("Authentication successful! You can close this window.", source=data_source)

    except Exception as e:
        print(f"OAuth callback failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

class OAuthCredentials(BaseModel):
    """Represents OAuth credentials for an integration."""
    access_token: str
    instance_url: Optional[str] = None

async def refresh_token(db, user_id, integration):
  latest_token_cred = db.query(Credential).filter(
    Credential.user_id == user_id,
    Credential.vendor == integration
  ).first()

  if not latest_token_cred or not latest_token_cred.refresh_token:
    raise HTTPException(status_code=400, detail="No refresh token found")

  try:
    decrypted_refresh = decrypt_token(latest_token_cred.refresh_token)
    client_id, client_secret = get_client_credentials(integration)

    payload = {
      'client_id': client_id,
      'client_secret': client_secret,
      'refresh_token': decrypted_refresh,
      'grant_type': 'refresh_token'
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    token_url = PROVIDER_CONFIG[integration]["token_url"]

    async with httpx.AsyncClient() as client:
      response = await client.post(token_url, data=payload, headers=headers)

    if response.status_code == 200:
      token_data = response.json()
      new_access_token = token_data['access_token']

      latest_token_cred.access_token = encrypt_token(new_access_token)
      latest_token_cred.token_expiry = datetime.utcnow() + timedelta(seconds=token_data['expires_in'])
      db.commit()

      return {'status': 'success', 'access_token': new_access_token}
    else:
      raise HTTPException(status_code=response.status_code, detail=response.text)

  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")

async def get_oauth_credentials(db: Session, user_id: int, integration: str) -> OAuthCredentials:
    """Get valid OAuth credentials, refreshing if needed."""
    latest_token = db.query(Credential).filter(
        Credential.user_id == user_id,
        Credential.vendor == integration,
        Credential.token_expiry > datetime.utcnow() + timedelta(seconds=300)
    ).first()

    if latest_token:
        return OAuthCredentials(
            access_token=decrypt_token(latest_token.access_token),
            instance_url=latest_token.instance_url
        )

    expired_token = db.query(Credential).filter(
        Credential.user_id == user_id,
        Credential.vendor == integration
    ).first()

    if not expired_token:
        raise HTTPException(status_code=401, detail="No credentials found. Please authorize.")

    if not expired_token.refresh_token:
        db.delete(expired_token)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials. Please reauthorize.")

    refresh_result = await refresh_token(db, user_id, integration)

    if refresh_result['status'] == 'success':
        return OAuthCredentials(
            access_token=refresh_result['access_token'],
            instance_url=expired_token.instance_url
        )

    raise HTTPException(status_code=401, detail="Token refresh failed. Please reauthorize.")

@auth_router.post('/oauth/getResources')
async def getResources(data_source: str = Body(...), config: dict = Body(...),
                       db=Depends(get_db), token: str = Depends(JWTBearer())):
  """Fetch data from an OAuth-connected provider. Provider-specific
  request building is handled by create_resource_request()."""
  user_id = get_user_id_from_token(token)
  credentials = await get_oauth_credentials(db, user_id, data_source)

  data_analyst = get_agent_with_token(token)
  data_analyst.activate_loader(data_source)

  url, headers, payload = create_resource_request(data_source, config, credentials.access_token, credentials.instance_url)
  tab_name = config.get('tabName', data_source)
  table_names = [tab_name]

  async with httpx.AsyncClient() as client:
    response = await client.get(url, headers=headers, params=payload)
    if response.status_code != 200:
      raise HTTPException(status_code=response.status_code, detail=response.text)
    response_data = response.json()

  joint_details = {
    'ssName': config.get('ssName', data_source),
    'description': config.get('description', f'Data fetched from {data_source}'),
    'globalExtension': data_source
  }
  success, done, detail = data_analyst.initial_pass(response_data, tab_name, 1, 1)

  if success:
    load_success, detail = data_analyst.upload_data(detail, joint_details)
    if load_success:
      return JSONResponse(status_code=200, content={'table': detail, 'all_tabs': table_names, 'done': done})
    else:
      raise HTTPException(status_code=400, detail=detail)
  else:
    raise HTTPException(status_code=400, detail=detail)

@auth_router.get('/oauth/{integration}')
async def integration_auth(integration: str, token: str = Depends(JWTBearer()), db = Depends(get_db)):
  if not token:
    raise HTTPException(status_code=400, detail="Invalid token")
  if integration not in PROVIDER_CONFIG:
    raise HTTPException(status_code=400, detail=f"{integration} not supported.")

  user_id = get_user_id_from_token(token)

  latest_token = db.query(Credential).filter(
    Credential.user_id == user_id, Credential.vendor == integration, Credential.token_expiry > datetime.utcnow()
  ).first()

  if latest_token:
    return create_oauth_response("Already authorized! You can close this window.", source=integration)

  try:
    refresh_result = await refresh_token(db, user_id, integration)
    if refresh_result['status'] == 'success':
      return create_oauth_response("Authorization refreshed! You can close this window.", source=integration)
  except HTTPException:
    pass

  state = f"{integration}.{user_id}"
  url = create_oauth_url(integration, state)
  return RedirectResponse(url, status_code=302)

@auth_router.post('/disconnectIntegration/{integration}', dependencies=[Security(JWTBearer())])
async def disconnect_integration(integration: str, token: str = Depends(JWTBearer()), db=Depends(get_db)):
  user_id = get_user_id_from_token(token)
  db.query(Credential).filter(
    Credential.user_id == user_id,
    Credential.vendor == integration
  ).delete()
  db.commit()
  return {'status': 'success'}

@auth_router.get('/integrationStatus/{integration}')
async def check_integration_status(integration: str, token: str = Depends(JWTBearer()), db=Depends(get_db)):
  try:
    user_id = get_user_id_from_token(token)

    latest_token = db.query(Credential).filter(
      Credential.user_id == user_id,
      Credential.vendor == integration,
      Credential.token_expiry > datetime.utcnow()
    ).first()

    if latest_token:
      return {'connected': True}

    try:
      refresh_result = await refresh_token(db, user_id, integration)
      return {'connected': refresh_result['status'] == 'success'}
    except HTTPException:
      return {'connected': False}

  except Exception as e:
    print(f"Error checking integration status: {str(e)}")
    return {'connected': False}

@auth_router.get('/auth/check')
async def check_authentication(request: Request, auth_token: str = Depends(JWTBearer())):
  """Check if the user is authenticated by verifying their JWT token."""
  try:
    token = get_token(request=request, auth_token=auth_token)
    if not token:
      return {"authenticated": False}

    payload = decode_JWT(token)

    return {
      "authenticated": True,
      "user": {
        "email": payload.get("email"),
        "userID": payload.get("userID")
      }
    }
  except HTTPException:
    return {"authenticated": False}
  except Exception:
    return {"authenticated": False}
