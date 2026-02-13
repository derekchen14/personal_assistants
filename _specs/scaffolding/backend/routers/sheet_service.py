import os
import json
import shutil
import asyncio
import traceback
from typing import List

from database.tables import Conversation, ConversationDataSource, DialogueState, Utterance, Frame, UserDataSource
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Security
from fastapi.responses import JSONResponse
from backend.auth.JWT_helpers import JWTBearer, decode_JWT

from pydantic import BaseModel, validator
from backend.auth.credentials import get_auth_user_email
from backend.assets.ontology import allowed_formats, default_limit
from backend.manager import get_agent_with_token, get_user_id_from_token
import pandas as pd
from backend.db import get_db

sheet_router = APIRouter()

class DriveFile(BaseModel):
  id: str
  name: str
  mimeType: str

  @validator('mimeType')
  def validate_mime_type(cls, v):
    allowed_types = [
      'application/vnd.google-apps.spreadsheet',
      'text/csv'
    ]
    if v not in allowed_types:
      raise ValueError(f'Invalid mime type. Must be one of: {", ".join(allowed_types)}')
    return v

# Data import from Google Drive
class DriveImport(BaseModel):
  files: List[DriveFile]

  @validator('files')
  def validate_files(cls, v):
    if not v:
      raise ValueError('At least one file must be selected')
    return v

class Spreadsheet(BaseModel):
  ssName: str
  tabNames: list

@sheet_router.post('/sheets/select')
async def select_sheet(spreadsheet: Spreadsheet, token: str = Depends(JWTBearer())):
  dir_name = spreadsheet.ssName
  for tab_name in spreadsheet.tabNames:
    table_location = os.path.join('database', 'storage', dir_name, f"{tab_name}.csv")

  data_analyst = get_agent_with_token(token)
  success, detail = data_analyst.upload_data(spreadsheet)
  
  if success:
    response = {'spreadsheet': dir_name, 'content': detail}
    return JSONResponse(status_code=200, content=response)
  else:
    raise HTTPException(status_code=400, detail=detail)

@sheet_router.get('/sheets/fetch')
async def fetch_table(tab_name: str, row_start: int=0, row_end: int=default_limit, token: str = Depends(JWTBearer())):
  data_analyst = get_agent_with_token(token)
  success, detail = data_analyst.fetch_tab_data(tab_name, row_start, row_end)
  if success:
    response = {'table': tab_name, 'content': detail, 'tabType': 'direct'}
    return JSONResponse(status_code=200, content=response)
  else:
    raise HTTPException(status_code=400, detail=detail)

@sheet_router.post('/sheets/upload')
# Processes file uploads for different spreadsheet formats. Handles both single and multi-tab
# uploads while validating file types and managing data loading into the system.
async def upload_sheet(file: UploadFile=File(...), sheetInfo: str=Form(...), position: str=Form(...), 
                      token: str = Depends(JWTBearer())):
  try:
    file_name, extension = os.path.splitext(file.filename.lower())
    extension = extension[1:]   # to convert '.csv' into 'csv'
    sheet_info = json.loads(sheetInfo)

    if extension not in list(allowed_formats.keys()):
      if extension in ['numbers', 'xlsm', 'xls']:
        detail = "Unsupported spreadsheet format. Please convert your file to CSV format and try again."
      else:
        detail = f"Invalid file type of {extension}"
      raise HTTPException(status_code=400, detail=detail)
    elif extension != sheet_info['globalExtension']:
      raise HTTPException(status_code=400, detail="File extension does not match global extension")

    pos = json.loads(position)  # {'index': 0, 'total': 2}
    is_multi_tab = pos['index'] < 0
    data_analyst = get_agent_with_token(token)
    data_analyst.activate_loader(extension, is_multi_tab)

    contents = await file.read()

    if is_multi_tab:
      result = await multi_tab_upload(contents, sheet_info, extension, data_analyst)
    else:
      result = await single_tab_upload(contents, sheet_info, pos, extension, data_analyst)
    return result
      
  except Exception as e:
    tb = traceback.extract_tb(e.__traceback__)
    # Filter for just our codebase files
    our_tb = [frame for frame in tb if 'backend/' in frame.filename or 'utils/' in frame.filename]
    error_trace = ''.join(traceback.format_list(our_tb))
    print(f"Error in upload_sheet: {str(e)}")
    print(f"Traceback:\n{error_trace}")
    raise HTTPException(status_code=500, detail=str(e))

async def single_tab_upload(contents: bytes, sheet_info: dict, pos: dict, extension: str, data_analyst):
  tab_name = sheet_info['tab']   # sheet_info has keys: [ssName, tab, description, globalExtension]
  success, done, detail = data_analyst.initial_pass(contents, tab_name, pos['index'], pos['total'])

  if success:
    if done:
      load_success, detail = data_analyst.upload_data(detail, sheet_info)
      if load_success:
        print(f"Loaded data into memory")  
        return JSONResponse(status_code=200, content={'table': detail, 'done': True, 
                             'properties': {tab_name: data_analyst.world.get_simplified_schema(tab_name)}})
      else:
        print(f"Failed to load into memory, details={detail}")
        raise HTTPException(status_code=400, detail=detail)
    else:
      print(f"Initial pass not done, details={detail} ")
      return JSONResponse(status_code=200, content=detail)
  else:
    print(f"Failed initial pass, details={detail} ")
    raise HTTPException(status_code=400, detail=detail)

async def multi_tab_upload(contents: bytes, sheet_info: dict, extension: str, data_analyst):
  success, table_names, error_msg = data_analyst.multi_tab_pass(contents, sheet_info)
  if not success:
    print(f"Failed to complete multi-tab pass, details={error_msg}")
    raise HTTPException(status_code=400, detail=f"Error processing multi-tab: {error_msg}")

  load_success, detail = data_analyst.upload_data(table_names, sheet_info)
  if load_success:
    properties = {table_name: data_analyst.world.get_simplified_schema(table_name) for table_name in table_names}
    return JSONResponse(status_code=200, content={'table': detail, 'done': True, 'properties': properties})
  else:
    print(f"Failed to load multi-tab data into memory, details={detail}")
    raise HTTPException(status_code=400, detail=detail)

@sheet_router.get('/sheets/user-sources')
async def get_user_sources(token: str = Depends(JWTBearer())):
  user_id = get_user_id_from_token(token)
  data_analyst = get_agent_with_token(token)
  
  # Get all data sources for this user
  sources = data_analyst.storage.get_user_sources(user_id)
  # Format the response
  formatted_sources = [{
    'id': str(source.id),
    'name': source.name,
    'provider': source.provider,
    'size_kb': source.size_kb,
    'created_at': source.created_at.isoformat() if source.created_at else None
  } for source in sources]
  
  return JSONResponse(status_code=200, content={'sources': formatted_sources})

@sheet_router.post('/sheets/load-source')
async def load_data_source(source_ids: str = Form(...), token: str = Depends(JWTBearer())):
  try:
    source_ids = json.loads(source_ids)
    user_id = get_user_id_from_token(token)
    data_analyst = get_agent_with_token(token)
    
    sources = data_analyst.storage.get_sources_by_ids(source_ids)

    table_dict = {}
    for source in sources:
      if source.user_id != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to data source")
      else:
        table_dict[source.name] = pd.DataFrame({
          col: data for col, data in zip(source.content['columns'], source.content['data'])
        })
    data_analyst.data_source_ids = source_ids
    properties = data_analyst.memory.register_new_data(
        ss_name='&'.join(source.name for source in sources),
        ss_goal=f'Loaded from {source.provider}',
        ss_data=table_dict
    )

    preview_frame = data_analyst.register_data_with_agent(properties)
    table_data = preview_frame.get_data('list')
    
    return JSONResponse(status_code=200, content={
      'table': table_data,
      'done': True,
      'properties': properties
    })
  except Exception as e:
    tb = traceback.extract_tb(e.__traceback__)
    # Filter for just our codebase files
    our_tb = [frame for frame in tb if 'backend/' in frame.filename or 'utils/' in frame.filename]
    error_trace = ''.join(traceback.format_list(our_tb))
    print(f"Error in load_data_source: {str(e)}")
    print(f"Traceback:\n{error_trace}")

@sheet_router.post('/sheets/generate-metadata')
async def generate_table_metadata(tables: dict, token: str = Depends(JWTBearer())):
  try:
    data_analyst = get_agent_with_token(token)
    metadata = data_analyst.generate_table_metadata(tables)
    return JSONResponse(status_code=200, content=metadata)
  except Exception as e:
    print(f"Error in generate_table_metadata: {str(e)}")
    print(f"Traceback:\n{e.__traceback__}")
    raise HTTPException(status_code=500, detail=str(e))

@sheet_router.delete('/sheets/user-sources/{source_id}')
async def delete_user_source(
    source_id: str,
    token: str = Depends(JWTBearer())
):
    try:
        user_id = get_user_id_from_token(token)
        session = get_db()
        
        try:
            # Get the source to verify ownership using the session
            source = session.query(UserDataSource).filter(
                UserDataSource.id == source_id
            ).first()
            
            if not source or source.user_id != user_id:
                raise HTTPException(status_code=403, detail="Unauthorized access to data source")
            
            # Get all conversation data sources for this source
            conv_data_sources = session.query(ConversationDataSource).filter(
                ConversationDataSource.data_source_id == source_id
            ).all()
            
            # For each conversation, check if it will have no sources left after deletion
            for conv_ds in conv_data_sources:
                # Count remaining sources for this conversation
                remaining_sources = session.query(ConversationDataSource).filter(
                    ConversationDataSource.conversation_id == conv_ds.conversation_id,
                    ConversationDataSource.data_source_id != source_id
                ).count()
                
                # If no sources left, delete the conversation and all its related data
                if remaining_sources == 0:
                    conversation = session.query(Conversation).filter(
                        Conversation.id == conv_ds.conversation_id
                    ).first()
                    
                    if conversation:
                        # Get all utterances for this conversation
                        utterances = session.query(Utterance).filter(
                            Utterance.conversation_id == conversation.id
                        ).all()
                        
                        # Delete dialogue states and frames first
                        for utterance in utterances:
                            session.query(DialogueState).filter(
                                DialogueState.utterance_id == utterance.id
                            ).delete()
                            
                            session.query(Frame).filter(
                                Frame.utterance_id == utterance.id
                            ).delete()
                        
                        # Delete the conversation (cascade will handle utterances and other related records)
                        session.delete(conversation)
            
            # Delete the source
            session.delete(source)
            session.commit()
            return {"status": "success", "message": "Data source and associated empty conversations deleted successfully"}
        finally:
            session.close()
            
    except Exception as e:
        print(f"Error in delete_user_source: {str(e)}")
        print(f"Traceback:\n{e.__traceback__}")
        raise HTTPException(status_code=500, detail=str(e))