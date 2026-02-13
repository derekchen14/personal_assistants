import os
import asyncio
import traceback
from typing import Optional
from fastapi import HTTPException, Body, Depends, APIRouter, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.auth.credentials import get_auth_user_email
from backend.auth.JWT_helpers import JWTBearer, decode_JWT
from backend.manager import get_agent_with_token, get_user_id_from_token

# Create a router for table operations
table_router = APIRouter(prefix="/api/table", tags=["table"])

# Define request models
class TableOperationRequest(BaseModel):
    action: str  # "delete" or "edit" 
    table_name: str

@table_router.delete("/{table_name}", dependencies=[Depends(JWTBearer())])
async def delete_table(
    table_name: str = Path(..., description="The name of the table to delete"),
    token: str = Depends(JWTBearer())
):
    """
    Delete a table by name using a REST-style DELETE endpoint.
    
    Args:
        table_name: The name of the table to delete (from URL path)
        token: The JWT token (injected by FastAPI)
        
    Returns:
        JSON response with the deletion result
    """
    try:
        # Get the data analyst agent using the token
        data_analyst = get_agent_with_token(token)
        user_id = get_user_id_from_token(token)        
        success, message = data_analyst.delete_data(table_name)
      
        if not success:
          raise HTTPException(status_code=400, detail=message)
            
        return {"status": "success", "message": message}
        
    except Exception as e:
        import traceback
        traceback.print_exc()        
        # Return error response
        raise HTTPException(status_code=500, detail=str(e))
