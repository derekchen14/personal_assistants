import os
from typing import List, Dict, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Security
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask
from backend.auth.JWT_helpers import JWTBearer

from backend.auth.credentials import get_auth_user_email
from backend.manager import get_agent_with_token, get_user_id_from_token

interaction_router = APIRouter()

class TableEdit(BaseModel):
  type: str
  row: int
  col: str
  originalValue: str
  newValue: str
  timestamp: str

class Manipulations(BaseModel):
  updates: List[TableEdit]
  tab_name: str

@interaction_router.post('/interactions/edit')
async def update_data(manipulations: Manipulations, token: str = Depends(JWTBearer())):
  data_analyst = get_agent_with_token(token)
  tab_name, changes = manipulations.tab_name, manipulations.updates
  tab_schema = data_analyst.world.metadata['schema'][tab_name]
  success, detail = data_analyst.memory.update_table(tab_name, tab_schema, changes)

  if success:
    return JSONResponse(status_code=200, content={'detail': detail})
  else:
    raise HTTPException(status_code=400, detail=detail)

class ExportData(BaseModel):
  sheetName: str
  tabName: str
  exportType: str
  fileName: str

@interaction_router.post('/interactions/download')
async def download_data(export_data: ExportData, token: str = Depends(JWTBearer())):
  data_analyst = get_agent_with_token(token)
  media_types = {'csv': 'text/csv', 'json': 'application/json',
                 'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
  media = media_types.get(export_data.exportType, None)

  if media:
    try:
      file_content = data_analyst.download_data(export_data.tabName, export_data.exportType)
    except Exception as ecp:
      raise HTTPException(status_code=400, detail=str(ecp))
  else:
    raise HTTPException(status_code=400, detail='Invalid export type:' + str(export_data.exportType))

  file_response = FileResponse(file_content.name, filename=export_data.fileName, media_type=media,
                                background=BackgroundTask(lambda: os.unlink(file_content.name)))
  return file_response

class Entity(BaseModel):
  tab: str
  col: str
  row: Optional[int]
  ver: bool
  rel: Optional[str]

class MetricData(BaseModel):
  flowType: str
  stage: str
  metric: str
  variables: Dict[str, List[Entity]]

class TimeRangeData(BaseModel):
  flowType: str
  stage: str
  time: Dict[str, str]

class TermGroup(BaseModel):
  flowType: str
  stage: str
  chosen: str
  source: Entity
  similar: List[str]

@interaction_router.post('/interactions/resolve/typo')
async def resolve_typo(term_group: TermGroup, token: str = Depends(JWTBearer())):
  data_analyst = get_agent_with_token(token)
  frame, response, success = data_analyst.user_interactions(term_group)
  response['tabType'] = frame.tab_type
  response['frame'] = frame.get_data('define')

  if success:
    return JSONResponse(status_code=200, content=response)
  else:
    return JSONResponse(status_code=500, content={'error': 'Something went wrong.'})

@interaction_router.post('/interactions/metric/two')
async def metric_two(request: Request, token: str = Depends(JWTBearer())):
  request_json = await request.json()
  if request_json['stage'] == 'time-range':
    analyze_data = TimeRangeData.parse_obj(request_json)
  else:
    analyze_data = MetricData.parse_obj(request_json)

  data_analyst = get_agent_with_token(token)
  frame, response, success = data_analyst.user_interactions(analyze_data)
  response['tabType'] = frame.tab_type
  response['frame'] = frame.get_data('json') if frame.tab_type == 'derived' else frame.get_data('define')

  if success:
    return JSONResponse(status_code=200, content=response)
  else:
    return JSONResponse(status_code=500, content={'error': 'Something went wrong.'})

class CodeData(BaseModel):
  flowType: str
  language: str
  code: str

@interaction_router.post('/interactions/command/code')
async def modify_code(query_data: CodeData, token: str = Depends(JWTBearer())):
  data_analyst = get_agent_with_token(token)
  frame, response = data_analyst.user_commands(query_data)
  response['frame'] = frame.get_data('json') if frame.tab_type == 'derived' else frame.get_data('define')
  return JSONResponse(status_code=200, content=response)

class CheckboxData(BaseModel):
  flowType: str
  stage: str
  checked: List[str]
  support: str = ''

@interaction_router.post('/interactions/checkbox')
async def handle_checkbox(raw_data: CheckboxData, token: str = Depends(JWTBearer())):
  data_analyst = get_agent_with_token(token)
  frame, response, success = data_analyst.user_interactions(raw_data)
  response['tabType'] = frame.tab_type
  response['frame'] = frame.get_data('define')

  if success:
    return JSONResponse(status_code=200, content=response)
  else:
    return JSONResponse(status_code=500, content={'error': 'Something went wrong.'})

class MergeData(BaseModel):
  flowType: str
  stage: str
  selected: List[Entity]
  style: Dict[str, str] = {}
  resolution: str = ''
  chosen: Optional[Dict[str, List[int]]] = {}
  method: str = 'manual'

@interaction_router.post('/interactions/merge')
# Handles data merging operations between different sources or tables. Processes merge
# configurations and returns updated frame data with merged results.
async def merge_flows(raw_data: MergeData, token: str = Depends(JWTBearer())):
  data_analyst = get_agent_with_token(token)
  frame, response, success = data_analyst.user_interactions(raw_data)
  response['tabType'] = frame.tab_type
  response['frame'] = frame.get_data('define')

  if success:
    return JSONResponse(status_code=200, content=response)
  else:
    return JSONResponse(status_code=500, content={'error': 'Something went wrong.'}) 