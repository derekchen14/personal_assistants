import os
import asyncio
import random
import traceback
from uuid import uuid4

from fastapi import (WebSocket, WebSocketDisconnect, APIRouter, Cookie)

from backend.auth.JWT_helpers import decode_JWT
from backend.assets.ontology import delay_responses
from backend.utilities.routing import build_json_response_for_state, build_json_response_for_frame
from backend.manager import get_agent_with_token, reset_agent_with_token, cleanup_agent_by_token, register_cleanup_callback, update_last_activity
from database.tables import Conversation, ConversationDataSource, Utterance, DialogueState, Frame

ENV = os.getenv("SOLEDA_ENV", "development")

# Global dictionaries to store active connections and message queues
websocket_connections = {}
queues = {}

# Create a router for the chat service
chat_router = APIRouter()

def get_queue(user_email: str):
  if user_email not in queues:
    queues[user_email] = asyncio.Queue()
  return queues[user_email]

def reset_agent_chat(user_email: str, token: str):
  """Reset the agent for a user using the token for auth"""
  reset_agent_with_token(token)
  return {'message': "Chat reset successfully!"}

# This function will be called when an agent is cleaned up by the manager
async def notify_agent_cleanup(user_id):
  try:
    user_email = None
    # Find the user's email from the websocket_connections keys
    for email, connection_info in websocket_connections.items():
      if connection_info.get("user_id") == user_id:
        user_email = email
        break
        
    if user_email and user_email in queues:
      disconnect_message = {
        "connection_status": "disconnected",
        "message": "Your session has timed out due to inactivity. Please import your data again."
      }
      await queues[user_email].put(disconnect_message)
  except Exception as e:
    print(f"Error notifying client of agent cleanup: {e}")

# Define the synchronous wrapper function that will be registered as the callback
def cleanup_notification_callback(user_id):
  """
  Wrapper function for the notify_agent_cleanup coroutine.
  This is the callback that will be registered with the manager.
  """
  try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
      asyncio.create_task(notify_agent_cleanup(user_id))
    else:
      # Run in a new event loop if we're not in an async context
      asyncio.run(notify_agent_cleanup(user_id))
  except Exception as e:
    print(f"Error in cleanup notification callback: {e}")

# Register the cleanup notification callback with the manager
register_cleanup_callback(cleanup_notification_callback)

@chat_router.websocket('/ws')
# Manages real-time WebSocket connections for chat functionality. Handles message processing,
# agent interactions, and streaming responses with background tasks for delay responses.
async def chat(websocket: WebSocket, auth_token: str = Cookie(None)):
  user_id = None
  user_email = None
  
  async def sender(queue):
    while True:
      try:
        message = await queue.get()
        await websocket.send_json(message)
      except WebSocketDisconnect as e:
        print(f"WebSocket disconnected with code: {e.code}")
        break
      except asyncio.CancelledError:
        print("WebSocket closed by client")
        break
      except Exception as e:
        print(f"Error occurred while processing message: {e}")

  async def stall_for_time(delay, queue):
    try:
      await asyncio.sleep(delay)
    except asyncio.CancelledError:
      print("  Delay is canceled")
      return
    payload = {'message': random.choice(delay_responses)}
    await queue.put(payload)

  # Authenticate with cookie token
  if not auth_token:
    await websocket.accept()
    await websocket.close(code=1008, reason="Authentication failed")
    return
  
  # Verify token validity
  try:
    payload = decode_JWT(auth_token)
    user_email = payload.get('email')
    user_id = payload.get('userID')
    if not user_email:
      await websocket.accept()
      await websocket.close(code=1008, reason="Invalid authentication token")
      return
  except Exception as e:
    await websocket.accept()
    await websocket.close(code=1008, reason="Invalid authentication token")
    return
  
  # If authentication succeeded, accept the connection
  await websocket.accept()
  
  # Set up the data analyst with the authenticated token
  data_analyst = get_agent_with_token(auth_token)
  queue = get_queue(user_email)
  sender_task = asyncio.create_task(sender(queue))
  
  # Store websocket connection
  websocket_connections[user_email] = {
    "websocket": websocket,
    "user_id": user_id
  }

  async def create_conversation():
    """Create a new conversation in the storage database"""
    try:
      id = uuid4()
      ss_name = data_analyst.memory.db_name
      # Temporarily skip making conversations for test data
      if ss_name == 'Shoe Store Sales' or ss_name == 'E-commerce Web Traffic' or ss_name == 'Customer Integration':
        return 'no_db_conversation'
      data_analyst.storage.insert_item(Conversation(
        id=id,
        name=data_analyst.memory.db_name,
        description=data_analyst.memory.description.get('goal', ''),
        user_id=user_id,
        agent_id=1, #Dana
        source="production" if ENV == "production" else "development",
      ))
      data_analyst.conversation_id = str(id)  # Convert UUID to string

      # Add entries to ConversationDataSource table for each data source
      for data_source_id in data_analyst.data_source_ids:
        data_analyst.storage.insert_item(ConversationDataSource(
          conversation_id=id,
          data_source_id=data_source_id
        ))

      return str(id)  # Return string version of UUID
    except Exception as e:
      print(f"Error creating conversation: {str(e)}")
      return None

  while True:
    try:      
      data_analyst = get_agent_with_token(auth_token)
      error_message = "Sorry, I couldn't process that request. Please try asking a simpler question or phrasing it differently. If the issue persists, contact us at support@soleda.ai."
      unsupported_message = "This request isn't supported yet, but we're working on it! Please try a different request or contact us at support@soleda.ai."
      body = await websocket.receive_json(mode='binary')
        
      user_actions, user_text, gold_dax = body['lastAction'], body['currentMessage'], body['dialogueAct']
      data_analyst.handle_user_actions(user_actions, gold_dax)

      """
      # Create conversation on first message if not exists
      if not data_analyst.conversation_id:
        conversation_id = await create_conversation()
        if not conversation_id:
          await queue.put({'message': "Error creating conversation. Please try again."})
          continue
      if data_analyst.conversation_id != 'no_db_conversation':
        utt_id = uuid4()
        data_analyst.storage.insert_item(Utterance(
          id=utt_id,
          conversation_id=data_analyst.conversation_id,
          speaker='User',
          text=user_text,
          utt_type='text',
          operations=user_actions if user_actions else [],
          dact_id=gold_dax if gold_dax else None
        ))
      """
      stall_task = asyncio.create_task(stall_for_time(24, queue))
      
      try:
        output, out_type = await asyncio.to_thread(data_analyst.understand_language, user_text, gold_dax)
        if out_type == 'error':
          await queue.put({**output, 'conversation_id': data_analyst.conversation_id})
        elif out_type == 'stream':
          stall_task.cancel()
          for chunk in output:
            stream_json, still_thinking = await asyncio.to_thread(data_analyst.process_thoughts, chunk)
            if still_thinking:
              await queue.put({**stream_json, 'conversation_id': data_analyst.conversation_id})

          thought_json = data_analyst.wrap_up_thinking()
          data_analyst.res.top_panel = thought_json
          stall_task = asyncio.create_task(stall_for_time(24, queue))
          dialogue_state = data_analyst.complete_nlu()
        elif out_type == 'state' and len(output.thought) > 0:
          thought_json = build_json_response_for_state(output)
          data_analyst.res.top_panel = thought_json
          await queue.put({**thought_json, 'conversation_id': data_analyst.conversation_id})
          stall_task.cancel()
          stall_task = asyncio.create_task(stall_for_time(24, queue))
        if out_type == 'unsupported':
          await queue.put({'message': unsupported_message, 'conversation_id': data_analyst.conversation_id})
          if 'stall_task' in locals() and stall_task:
            stall_task.cancel()
          continue

        take_action = True
        while take_action:
          frame, actions, take_action = await asyncio.to_thread(data_analyst.execute_policy)

          if len(frame.code) > 0 or frame.source == 'change':
            frame_json = build_json_response_for_frame(frame)
            if frame_json['interaction']['show']:
              data_analyst.res.top_panel = frame_json

            if frame.properties.get('respond', False):
              response, _ = await asyncio.to_thread(data_analyst.generate_response, frame, actions)
              await queue.put({**response, 'conversation_id': data_analyst.conversation_id})
            elif 'CREATION' in actions:
              pass
            else:
              await queue.put({**frame_json, 'conversation_id': data_analyst.conversation_id})

            stall_task.cancel()
            stall_task = asyncio.create_task(stall_for_time(24, queue))

        response, _ = await asyncio.to_thread(data_analyst.generate_response, frame, actions)
        await queue.put({**response, 'conversation_id': data_analyst.conversation_id})
        if user_id:
          update_last_activity(user_id)
        stall_task.cancel()
      
      except Exception as main_error:
        await queue.put({'message': error_message, 'conversation_id': data_analyst.conversation_id})
        print(f"Error: {str(main_error)}\n{traceback.format_exc()}")
        if 'stall_task' in locals() and stall_task:
          stall_task.cancel()
      
    except WebSocketDisconnect as wsd:
      close_code = wsd.code
      close_reason = getattr(wsd, 'reason', 'No reason provided')
      print(f"WebSocket disconnected with code: {close_code}, reason: {close_reason}")
            
      if auth_token and 'data_analyst' in locals():
        # Call end_session before cleanup
        try:
          data_analyst.close()
        except Exception as e:
          print(f"Error saving session state: {str(e)}")
        cleanup_agent_by_token(auth_token, 'websocket')
      
      if user_email and user_email in websocket_connections:
        del websocket_connections[user_email]
          
      if 'sender_task' in locals() and sender_task:
        sender_task.cancel()
      break
    except asyncio.CancelledError:
      print("WebSocket closed by client")
      
      if auth_token and 'data_analyst' in locals():
        cleanup_agent_by_token(auth_token, 'websocket')
      
      if user_email and user_email in websocket_connections:
        del websocket_connections[user_email]
          
      if 'sender_task' in locals() and sender_task:
        sender_task.cancel()

      break
    except Exception as error:
      print(f"Unexpected error in chat WebSocket handler: {str(error)}\n{traceback.format_exc()}")
      
      if auth_token and 'data_analyst' in locals():
        cleanup_agent_by_token(auth_token, 'websocket')
      
      if user_email and user_email in websocket_connections:
        del websocket_connections[user_email]
          
      try:
        await queue.put({'message': error_message, 'conversation_id': data_analyst.conversation_id})
      except:
        pass

  if 'sender_task' in locals() and sender_task:
    sender_task.cancel()