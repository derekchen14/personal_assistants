import asyncio
import traceback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.manager import get_or_create_agent, cleanup_agent, reset_agent
from backend.utilities.services import PostService

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

        post_svc = PostService()
        posts_result = post_svc.search()
        post_items = posts_result.get('result', [])

        welcome_frame = {
            'type': 'list',
            'show': True,
            'data': {'title': 'Your Posts', 'items': post_items},
            'source': 'welcome',
            'panel': 'top',
        } if post_items else None

        welcome_response = {
            'message': f"Hey {username}! What are we writing today?",
            'raw_utterance': '',
            'actions': [],
            'interaction': {'type': 'default', 'show': False, 'data': {}},
            'code_snippet': None,
            'frame': welcome_frame,
        }

        await queue.put(welcome_response)

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

                if body.get('reset'):
                    reset_agent(username)
                    post_svc_r = PostService()
                    posts_r = post_svc_r.search()
                    items_r = posts_r.get('result', [])
                    reset_frame = {
                        'type': 'list',
                        'show': True,
                        'data': {'title': 'Your Posts', 'items': items_r},
                        'source': 'welcome',
                        'panel': 'top',
                    } if items_r else None
                    await queue.put({
                        'message': f"Hey {username}! What are we writing today?",
                        'raw_utterance': '',
                        'actions': [],
                        'interaction': {'type': 'default', 'show': False, 'data': {}},
                        'code_snippet': None,
                        'frame': reset_frame,
                    })
                    continue

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
