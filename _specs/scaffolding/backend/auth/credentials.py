from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.auth.JWT_helpers import decode_JWT

def get_auth_user_email(authorization: HTTPAuthorizationCredentials = Security(HTTPBearer())):
  credentials_exception = HTTPException(
    status_code=401,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
  )

  if authorization and authorization.scheme.lower() == "bearer":
    access_token = authorization.credentials
    # print(f"Token: {access_token}")
    payload = decode_JWT(access_token)
    user_email: str = payload.get("email")
    if user_email is None:
      raise credentials_exception
    return user_email
  raise credentials_exception
