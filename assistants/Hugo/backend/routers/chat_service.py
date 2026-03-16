import asyncio
import traceback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.manager import get_or_create_agent, cleanup_agent, reset_agent
from backend.utilities.services import PostService
from backend.components.dialogue_state import DialogueState


chat_router = APIRouter()

websocket_connections: dict = {}
queues: dict = {}


def _build_update_frames(result: dict, post_svc) -> tuple[dict, dict | None]:
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
    all_items = post_svc.list_preview().get('result', [])
    if post.get('status') == 'note':
        note_items = [it for it in all_items if it.get('status') == 'note']
        refresh_frame = {
            'type': 'grid',
            'show': True,
            'data': {'items': note_items, 'source': 'welcome'},
            'source': 'welcome',
            'panel': 'top',
        } if note_items else None
    else:
        refresh_frame = {
            'type': 'list',
            'show': True,
            'data': {'title': 'Your Posts', 'items': all_items, 'source': 'welcome'},
            'source': 'welcome',
            'panel': 'top',
        } if all_items else None
    return card_frame, refresh_frame



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
        sync = post_svc.sync_check()
        posts_result = post_svc.list_preview()
        post_items = posts_result.get('result', [])

        welcome_frame = {
            'type': 'list',
            'show': True,
            'data': {'title': 'Your Posts', 'items': post_items, 'source': 'welcome'},
            'source': 'welcome',
            'panel': 'top',
        } if post_items else None

        if sync['missing']:
            titles = ', '.join(f'"{m["title"]}"' for m in sync['missing'])
            s = 's' if len(sync['missing']) > 1 else ''
            welcome_message = (
                f"Hey {first_name}! Heads up — {titles} "
                f"{'are' if s else 'is'} listed in your index but the file{s} "
                f"can't be found on disk. You may want to restore or remove the entr{'ies' if s else 'y'}."
            )
        elif sync['added']:
            titles = ', '.join(f'"{a["title"]}"' for a in sync['added'])
            it = 'them' if len(sync['added']) > 1 else 'it'
            welcome_message = (
                f"Hey {first_name}! I noticed {titles} "
                f"{'were' if len(sync['added']) > 1 else 'was'} manually added since your last session "
                f"— I've registered {it} in your index."
            )
        else:
            welcome_message = f"Hey {first_name}! What are we writing today?"

        welcome_response = {
            'message': welcome_message,
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
                        state = DialogueState(agent.config)
                        agent.world.insert_state(state)
                    state.active_post = select_post_id
                    continue

                delete_post_id = body.get('delete_post')
                if delete_post_id:
                    try:
                        post_svc_d = PostService()
                        result = post_svc_d.delete(delete_post_id)
                        if result.get('status') == 'success':
                            posts_after = post_svc_d.list_preview()
                            items_after = posts_after.get('result', [])
                            deleted_status = result['result'].get('status', '')
                            frame_type = 'grid' if deleted_status == 'note' else 'list'
                            refresh_frame = {
                                'type': frame_type, 'show': True, 'panel': 'top',
                                'source': 'welcome',
                                'data': {'title': 'Your Posts', 'items': items_after, 'source': 'welcome'},
                            } if items_after else None
                            msg = '' if deleted_status == 'note' else f"Deleted \"{result['result']['title']}\"."
                            await queue.put({
                                'message': msg,
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

                create_post_type = body.get('create_post')
                if create_post_type:
                    title = body.get('title', '')
                    note_body = body.get('body', '')
                    try:
                        post_svc_c = PostService()
                        if create_post_type == 'note':
                            if len(note_body.strip()) < 2:
                                await queue.put({'message': 'Note body must be at least 2 characters.'})
                                continue
                            result = post_svc_c.create('', type='note', topic=note_body)
                            success_msg = ''
                        else:
                            result = post_svc_c.create(title, type=create_post_type)
                            success_msg = f'Created "{result["result"]["title"]}".' if result.get('status') == 'success' else ''
                        if result.get('status') == 'success':
                            all_items = post_svc_c.list_preview().get('result', [])
                            frame_type = 'grid' if create_post_type == 'note' else 'list'
                            refresh_frame = {
                                'type': frame_type, 'show': True, 'panel': 'top',
                                'source': 'welcome',
                                'data': {'title': 'Your Posts', 'items': all_items, 'source': 'welcome'},
                            }
                            await queue.put({
                                'message': '',
                                'raw_utterance': '',
                                'actions': [],
                                'interaction': {'type': 'default', 'show': False, 'data': {}},
                                'code_snippet': None,
                                'frame': refresh_frame,
                            })
                            if create_post_type == 'draft':
                                post = result['result']
                                card_frame = {
                                    'type': 'card', 'show': True, 'panel': 'bottom',
                                    'source': 'create',
                                    'data': {
                                        'post_id': post['post_id'],
                                        'title': post['title'],
                                        'status': post['status'],
                                        'content': post.get('content', ''),
                                        'source': 'create',
                                    },
                                }
                                await queue.put({
                                    'message': success_msg,
                                    'raw_utterance': '',
                                    'actions': [],
                                    'interaction': {'type': 'default', 'show': False, 'data': {}},
                                    'code_snippet': None,
                                    'frame': card_frame,
                                })
                        else:
                            await queue.put({'message': result.get('message', error_message)})
                    except Exception as create_error:
                        print(f'Create error: {create_error}\n{traceback.format_exc()}')
                        await queue.put({'message': error_message})
                    continue

                update_post_id = body.get('update_post')
                if update_post_id:
                    updates = body.get('updates', {})
                    try:
                        post_svc_u = PostService()
                        result = post_svc_u.update(update_post_id, updates)
                        if result.get('status') == 'success':
                            card_frame, list_frame = _build_update_frames(result, post_svc_u)
                            is_note = result['result'].get('status') == 'note'
                            if list_frame:
                                await queue.put({
                                    'message': '',
                                    'raw_utterance': '',
                                    'actions': [],
                                    'interaction': {'type': 'default', 'show': False, 'data': {}},
                                    'code_snippet': None,
                                    'frame': list_frame,
                                })
                            if not is_note:
                                post_title = result['result'].get('title', '')
                                await queue.put({
                                    'message': f'Updated "{post_title}".',
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
                dax = body.get('dax')
                payload = body.get('payload') or {}
                try:
                    result = await asyncio.to_thread(agent.take_turn, user_text, dax, payload)
                    frame = result.get('frame') or {}
                    if frame.get('source') == 'create' and (frame.get('data') or {}).get('status') == 'note':
                        all_items = PostService().list_preview().get('result', [])
                        note_items = [it for it in all_items if it.get('status') == 'note']
                        if note_items:
                            await queue.put({
                                'message': '',
                                'raw_utterance': '',
                                'actions': [],
                                'interaction': {'type': 'default', 'show': False, 'data': {}},
                                'code_snippet': None,
                                'frame': {
                                    'type': 'grid', 'show': True, 'panel': 'top',
                                    'source': 'welcome',
                                    'data': {'items': note_items, 'source': 'welcome'},
                                },
                            })
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
