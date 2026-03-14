import asyncio
import traceback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.manager import get_or_create_agent, cleanup_agent, reset_agent
from backend.utilities.services import PostService

chat_router = APIRouter()

websocket_connections: dict = {}
queues: dict = {}


def _validate_action_text(user_text: str) -> bool:
    """Check that every segment in an action payload has key=value format."""
    if not user_text:
        return False
    for segment in user_text.split(','):
        if '=' not in segment:
            return False
    return True


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

        first_name = username.split()[0] if username else username
        agent = get_or_create_agent(username)
        queue = _get_queue(username)

        post_svc = PostService()
        posts_result = post_svc.list_preview()
        post_items = posts_result.get('result', [])

        welcome_frame = {
            'type': 'list',
            'show': True,
            'data': {'title': 'Your Posts', 'items': post_items, 'source': 'welcome'},
            'source': 'welcome',
            'panel': 'top',
        } if post_items else None

        welcome_response = {
            'message': f"Hey {first_name}! What are we writing today?",
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
                    posts_r = post_svc_r.list_preview()
                    items_r = posts_r.get('result', [])
                    reset_frame = {
                        'type': 'list',
                        'show': True,
                        'data': {'title': 'Your Posts', 'items': items_r, 'source': 'welcome'},
                        'source': 'welcome',
                        'panel': 'top',
                    } if items_r else None
                    await queue.put({
                        'message': f"Hey {first_name}! What are we writing today?",
                        'raw_utterance': '',
                        'actions': [],
                        'interaction': {'type': 'default', 'show': False, 'data': {}},
                        'code_snippet': None,
                        'frame': reset_frame,
                    })
                    continue

                select_post_id = body.get('select_post')
                if select_post_id:
                    state = agent.world.current_state()
                    if not state:
                        from backend.components.dialogue_state import DialogueState
                        state = DialogueState(agent.config)
                        agent.world.insert_state(state)
                    state.active_post = select_post_id
                    continue

                create_post_type = body.get('create_post')
                if create_post_type:
                    action_text = f'type={create_post_type}'
                    if not _validate_action_text(action_text):
                        await queue.put({'message': error_message})
                        continue
                    try:
                        result = await asyncio.to_thread(
                            agent.take_turn, action_text,
                            [{'dax': '{05A}'}],
                        )
                        await queue.put(result)
                    except Exception as turn_error:
                        print(f'Turn error: {turn_error}\n{traceback.format_exc()}')
                        await queue.put({'message': error_message})
                    continue

                view_post_id = body.get('view_post')
                if view_post_id:
                    state = agent.world.current_state()
                    if not state:
                        from backend.components.dialogue_state import DialogueState
                        state = DialogueState(agent.config)
                        agent.world.insert_state(state)
                    state.active_post = view_post_id
                    action_text = f'source={view_post_id}'
                    if not _validate_action_text(action_text):
                        await queue.put({'message': error_message})
                        continue
                    try:
                        result = await asyncio.to_thread(
                            agent.take_turn, action_text,
                            [{'dax': '{1AD}'}],
                        )
                        await queue.put(result)
                    except Exception as turn_error:
                        print(f'Turn error: {turn_error}\n{traceback.format_exc()}')
                        await queue.put({'message': error_message})
                    continue

                delete_post_id = body.get('delete_post')
                if delete_post_id:
                    try:
                        post_svc_d = PostService()
                        result = post_svc_d.delete(delete_post_id)
                        if result.get('status') == 'success':
                            posts_after = post_svc_d.list_preview()
                            items_after = posts_after.get('result', [])
                            refresh_frame = {
                                'type': 'list',
                                'show': True,
                                'data': {'title': 'Your Posts', 'items': items_after, 'source': 'welcome'},
                                'source': 'welcome',
                                'panel': 'top',
                            } if items_after else None
                            await queue.put({
                                'message': f"Deleted \"{result['result']['title']}\".",
                                'raw_utterance': '',
                                'actions': [],
                                'interaction': {'type': 'default', 'show': False, 'data': {}},
                                'code_snippet': None,
                                'frame': refresh_frame,
                            })
                        else:
                            await queue.put({'message': result.get('message', error_message)})
                    except Exception as del_error:
                        print(f'Delete error: {del_error}\n{traceback.format_exc()}')
                        await queue.put({'message': error_message})
                    continue

                update_post_id = body.get('update_post')
                if update_post_id:
                    updates = body.get('updates', {})
                    try:
                        post_svc_u = PostService()
                        result = post_svc_u.update(update_post_id, updates)
                        if result.get('status') == 'success':
                            post = result['result']
                            card_frame = {
                                'type': 'card',
                                'show': True,
                                'data': {
                                    'post_id': post.get('post_id', ''),
                                    'title': post.get('title', ''),
                                    'status': post.get('status', ''),
                                    'content': post.get('content', ''),
                                },
                                'source': 'update',
                                'panel': 'bottom',
                            }
                            # Also refresh the list panel
                            posts_after = post_svc_u.list_preview()
                            items_after = posts_after.get('result', [])
                            list_frame = {
                                'type': 'list',
                                'show': True,
                                'data': {'title': 'Your Posts', 'items': items_after, 'source': 'welcome'},
                                'source': 'welcome',
                                'panel': 'top',
                            } if items_after else None
                            if list_frame:
                                await queue.put({
                                    'message': '',
                                    'raw_utterance': '',
                                    'actions': [],
                                    'interaction': {'type': 'default', 'show': False, 'data': {}},
                                    'code_snippet': None,
                                    'frame': list_frame,
                                })
                            await queue.put({
                                'message': f"Updated \"{post.get('title', '')}\".",
                                'raw_utterance': '',
                                'actions': [],
                                'interaction': {'type': 'default', 'show': False, 'data': {}},
                                'code_snippet': None,
                                'frame': card_frame,
                            })
                        else:
                            await queue.put({'message': result.get('message', error_message)})
                    except Exception as upd_error:
                        print(f'Update error: {upd_error}\n{traceback.format_exc()}')
                        await queue.put({'message': error_message})
                    continue

                user_text = body.get('text', '') or body.get('currentMessage', '')
                user_actions = body.get('lastAction', [])
                gold_dax = body.get('dialogueAct', None)

                try:
                    result = await asyncio.to_thread(
                        agent.take_turn, user_text, user_actions, gold_dax,
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
