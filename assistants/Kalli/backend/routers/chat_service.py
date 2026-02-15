"""WebSocket chat endpoint."""

import asyncio
import traceback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.manager import get_or_create_agent, cleanup_agent

chat_router = APIRouter()

websocket_connections: dict = {}
queues: dict = {}


def _get_queue(username: str) -> asyncio.Queue:
    if username not in queues:
        queues[username] = asyncio.Queue()
    return queues[username]


@chat_router.websocket('/ws')
async def chat(websocket: WebSocket):
    username = None
    await websocket.accept()

    error_message = (
        "Sorry, I couldn't process that request. Please try rephrasing."
    )

    try:
        intro = await websocket.receive_json()
        username = intro.get('username', '').strip()
        if not username:
            await websocket.send_json({'error': 'Username required'})
            await websocket.close(code=1008, reason='Username required')
            return

        agent = get_or_create_agent(username)
        queue = _get_queue(username)

        await queue.put({
            'message': f'Hey {username}! I\'m Kalli. What would you like to build today?',
            'raw_utterance': '',
            'actions': [],
            'interaction': {'type': 'default', 'show': False, 'data': {}},
            'code_snippet': None,
            'frame': None,
        })

        async def sender(q: asyncio.Queue):
            while True:
                try:
                    message = await q.get()
                    await websocket.send_json(message)
                except (WebSocketDisconnect, asyncio.CancelledError):
                    break
                except Exception as e:
                    print(f'WebSocket send error: {e}')

        sender_task = asyncio.create_task(sender(queue))
        websocket_connections[username] = websocket

        while True:
            try:
                body = await websocket.receive_json()

                user_text = body.get('text', '') or body.get('currentMessage', '')
                user_actions = body.get('lastAction', [])
                gold_dax = body.get('dialogueAct', None)

                try:
                    result = await asyncio.to_thread(
                        agent.handle_turn, user_text, user_actions, gold_dax,
                    )
                    await queue.put(result)
                except Exception as turn_error:
                    print(f'Turn error: {turn_error}\n{traceback.format_exc()}')
                    await queue.put({'message': error_message})

            except WebSocketDisconnect:
                break
            except asyncio.CancelledError:
                break
            except Exception as error:
                print(f'Unexpected WS error: {error}\n{traceback.format_exc()}')
                try:
                    await queue.put({'message': error_message})
                except Exception:
                    pass
                break

        sender_task.cancel()

    finally:
        if username:
            websocket_connections.pop(username, None)
            cleanup_agent(username, 'websocket')
