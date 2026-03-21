import asyncio
import traceback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.manager import get_or_create_agent, cleanup_agent, reset_agent
from backend.utilities.services import PostService
from backend.components.dialogue_state import DialogueState

chat_router = APIRouter()
websocket_connections: dict = {}
queues: dict = {}

_ERROR_MESSAGE = "Sorry, I couldn't process that request. Please try rephrasing."

def _get_queue(username:str) -> asyncio.Queue:
    if username not in queues:
        queues[username] = asyncio.Queue()
    return queues[username]


async def reset(username:str, queue:asyncio.Queue, first_name:str=''):
    reset_agent(username)
    post_service = PostService()
    posts_r = post_service.list_preview()
    items_r = posts_r.get('items', [])
    reset_frame = None
    if items_r:
        reset_frame = {'block_type': 'list', 'panel': 'top', 'origin': 'welcome'}
        reset_frame['data'] = {'title': 'Your Posts', 'items': items_r}
    
    start_message = f"Hey {first_name}! What are we writing today?"
    reset_panel = {'message': start_message, 'raw_utterance': '', 'actions': [], 'frame': reset_frame}
    await queue.put(reset_panel)

async def refresh_posts(body:dict, queue:asyncio.Queue):
    post_service = PostService()
    items = post_service.list_preview().get('items', [])
    frame_type = body.get('frame_type', 'list')
    refresh_frame = {'block_type': frame_type, 'panel': 'top', 'origin': 'welcome'}
    refresh_frame['data'] = {'title': 'Your Posts', 'items': items}
    refresh_panel = {'message': '', 'raw_utterance': '', 'actions': [], 'frame': refresh_frame}
    await queue.put(refresh_panel)

async def create_post(body:dict, queue:asyncio.Queue):
    post_type = body.get('create_post')
    title = body.get('title', '')
    try:
        post_service = PostService()
        if post_type == 'note':
            note_body = body.get('body', '')
            if len(note_body.strip()) < 2:
                await queue.put({'message': 'Note body must be at least 2 characters.'})
                return
            result = post_service.create_post('', type='note', topic=note_body)
            block_type = 'grid'
        else:
            result = post_service.create_post(title, type=post_type)
            block_type = 'list'
        if result.get('_success'):
            all_items = post_service.list_preview().get('items', [])
            page_frame = {'block_type': block_type, 'panel': 'top', 'origin': 'welcome'}
            page_frame['data'] = {'title': 'Your Posts', 'items': all_items}
            top_panel = {'message': '', 'raw_utterance': '', 'actions': [], 'frame': page_frame}
            await queue.put(top_panel)
            if post_type == 'draft':
                post_id, status = result.get('post_id', ''), result.get('status', '')
                success_msg = f'Created "{result.get("title", title)}".'
                draft_frame = {'block_type': 'card', 'panel': 'bottom', 'origin': 'create'}
                draft_frame['data'] = {'post_id': post_id, 'status': status, 'title': title, 'content': ''}
                bottom_panel = {'message': success_msg, 'raw_utterance': '', 'actions': [], 'frame': draft_frame}
                await queue.put(bottom_panel)
        else:
            await queue.put({'message': result.get('_message', _ERROR_MESSAGE)})
    except Exception as ecp:
        print(f'Create error: {ecp}\n{traceback.format_exc()}')
        await queue.put({'message': _ERROR_MESSAGE})

async def read_post(body:dict, agent, queue:asyncio.Queue):
    post_id = body.get('read_post')
    state = agent.world.current_state()
    if not state:
        state = DialogueState(agent.config)
        agent.world.insert_state(state)
    state.active_post = post_id
    if not body.get('view'):
        return
    post_service = PostService()
    meta = post_service.read_metadata(post_id)
    if not meta.get('_success'):
        return
    sections = meta.get('section_ids', [])
    content_parts = []
    for sec_id in sections:
        sec = post_service.read_section(post_id, sec_id)
        if sec.get('_success'):
            title, content = sec.get('title', sec_id), sec.get('content', '')
            final = content if title == '_hidden_section_title' else f'## {title}\n{content}'
            content_parts.append(final)
    view_frame = {'block_type': 'card', 'panel': 'bottom', 'origin': 'view'}
    view_frame['data'] = {
        'title': meta.get('title', ''), 'status': meta.get('status', ''),
        'post_id': post_id, 'content': '\n\n'.join(content_parts),
        'section_ids': sections,
    }
    view_panel = {'message': '', 'raw_utterance': '', 'actions': [], 'frame': view_frame}
    await queue.put(view_panel)

async def update_post(body:dict, queue:asyncio.Queue):
    post_id = body.get('update_post')
    updates = body.get('updates', {})
    try:
        post_service = PostService()
        new_content = updates.pop('content', None)
        if new_content is not None:
            stripped = new_content.lstrip()
            if stripped and not stripped.startswith('#'):
                new_content = '## _hidden_section_title\n\n' + new_content
            sections = post_service._extract_sections(new_content)
            entries = post_service._load_metadata()
            ent = post_service._find_entry(entries, post_id)
            if ent and sections:
                post_service._save_section_content(ent, sections)
                post_service._save_metadata(entries)
        if updates:
            post_service.update_post(post_id, updates)
        content_parts = []
        meta = post_service.read_metadata(post_id)
        title, status = meta.get('title', ''), meta.get('status', '')
        if meta.get('_success'):
            for sec_id in meta.get('section_ids', []):
                sec = post_service.read_section(post_id, sec_id)
                if sec.get('_success'):
                    sec_title, content = sec.get('title', sec_id), sec.get('content', '')
                    final = content if sec_title == '_hidden_section_title' else f'## {sec_title}\n{content}'
                    content_parts.append(final)
            update_frame = {'block_type': 'card', 'panel': 'bottom', 'origin': 'update'}
            content = '\n\n'.join(content_parts)
            update_frame['data'] = {'post_id': post_id, 'title': title, 'status': status, 'content': content}
            update_panel = {'message': '', 'raw_utterance': '', 'actions': [], 'frame': update_frame}
            await queue.put(update_panel)
        else:
            await queue.put({'message': meta.get('_message', _ERROR_MESSAGE)})
    except Exception as ecp:
        print(f'Update error: {ecp}\n{traceback.format_exc()}')
        await queue.put({'message': _ERROR_MESSAGE})

async def delete_post(body:dict, queue:asyncio.Queue):
    post_id = body.get('delete_post')
    try:
        post_service = PostService()
        pre_meta = post_service.read_metadata(post_id)
        was_note = pre_meta.get('status') == 'note' if pre_meta.get('_success') else False
        block_type = 'grid' if was_note else 'list'
        result = post_service.delete_post(post_id)
        if result.get('_success'):
            items = post_service.list_preview().get('items', [])
            page_frame = {'block_type': block_type, 'panel': 'top', 'origin': 'welcome'}
            page_frame['data'] = {'title': 'Your Posts', 'items': items}
            top_panel = {'message': '', 'raw_utterance': '', 'actions': [], 'frame': page_frame}
        else:
            top_panel = {'message': result.get('_message', _ERROR_MESSAGE)}
        await queue.put(top_panel)
    except Exception as ecp:
        print(f'Delete error: {ecp}\n{traceback.format_exc()}')
        await queue.put({'message': _ERROR_MESSAGE})


async def _send_grid_refresh(queue:asyncio.Queue):
    items = PostService().list_preview().get('items', [])
    frame = {'block_type': 'grid', 'panel': 'top', 'origin': 'welcome'}
    frame['data'] = {'title': 'Your Posts', 'items': items}
    await queue.put({'message': '', 'raw_utterance': '', 'actions': [], 'frame': frame})


async def create_note(body:dict, queue:asyncio.Queue):
    body_text = body.get('body', '')
    stripped = body_text.strip()
    if len(stripped) < 2 or len(stripped) > 2048:
        await queue.put({'message': 'Note body must be between 2 and 2048 characters.'})
        return
    try:
        result = PostService().create_post('', type='note', topic=body_text)
        if result.get('_success'):
            await _send_grid_refresh(queue)
        else:
            await queue.put({'message': result.get('_message', _ERROR_MESSAGE)})
    except Exception as ecp:
        print(f'Create note error: {ecp}\n{traceback.format_exc()}')
        await queue.put({'message': _ERROR_MESSAGE})


async def update_note(body:dict, queue:asyncio.Queue):
    note_id = body.get('update_note')
    body_text = body.get('body', '')
    stripped = body_text.strip()
    if len(stripped) < 2 or len(stripped) > 2048:
        await queue.put({'message': 'Note body must be between 2 and 2048 characters.'})
        return
    try:
        post_service = PostService()
        entries = post_service._load_metadata()
        ent = post_service._find_entry(entries, note_id)
        if ent:
            filepath = post_service._content_dir / ent['filename']
            filepath.write_text(body_text, encoding='utf-8')
            ent['updated_at'] = post_service._now()
            post_service._save_metadata(entries)
        await _send_grid_refresh(queue)
    except Exception as ecp:
        print(f'Update note error: {ecp}\n{traceback.format_exc()}')
        await queue.put({'message': _ERROR_MESSAGE})


async def delete_note(body:dict, queue:asyncio.Queue):
    note_id = body.get('delete_note')
    try:
        result = PostService().delete_post(note_id)
        if result.get('_success'):
            await _send_grid_refresh(queue)
        else:
            await queue.put({'message': result.get('_message', _ERROR_MESSAGE)})
    except Exception as ecp:
        print(f'Delete note error: {ecp}\n{traceback.format_exc()}')
        await queue.put({'message': _ERROR_MESSAGE})


@chat_router.websocket('/ws')
async def chat(websocket:WebSocket):
    username = None
    await websocket.accept()

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

        post_service = PostService()
        sync = post_service.sync_check()
        posts_result = post_service.list_preview()
        post_items = posts_result.get('items', [])

        welcome_frame = {
            'block_type': 'list',
            'data': {'title': 'Your Posts', 'items': post_items},
            'origin': 'welcome',
            'panel': 'top',
        } if post_items else None

        if sync['missing']:
            titles = ', '.join(f'"{item["title"]}"' for item in sync['missing'])
            suffix = 's' if len(sync['missing']) > 1 else ''
            welcome_message = (
                f"Hey {first_name}! Heads up — {titles} "
                f"{'are' if suffix else 'is'} listed in your index but the file{suffix} "
                f"can't be found on disk. You may want to restore or remove the entr{'ies' if suffix else 'y'}."
            )
        elif sync['added']:
            titles = ', '.join(f'"{item["title"]}"' for item in sync['added'])
            it = 'them' if len(sync['added']) > 1 else 'it'
            welcome_message = (
                f"Hey {first_name}! I noticed {titles} "
                f"{'were' if len(sync['added']) > 1 else 'was'} manually added since your last session "
                f"— I've registered {it} in your index."
            )
        else:
            welcome_message = f"Hey {first_name}! What are we writing today?"

        welcome_panel = {'message': welcome_message, 'raw_utterance': '', 'actions': [], 'frame': welcome_frame}
        await queue.put(welcome_panel)

        async def sender(queue:asyncio.Queue):
            while True:
                try:
                    message = await queue.get()
                    await websocket.send_json(message)
                except (WebSocketDisconnect, asyncio.CancelledError):
                    break
                except Exception as ecp:
                    print(f'WebSocket send error: {ecp}')

        sender_task = asyncio.create_task(sender(queue))
        websocket_connections[username] = websocket

        while True:
            try:
                body = await websocket.receive_json()

                api_category = ''
                for category in ['reset', 'refresh_posts', 'create_post', 'read_post', 'update_post', 'delete_post', 'create_note', 'update_note', 'delete_note']:
                    if body.get(category) is not None:
                        api_category = category
                        break

                if api_category == 'reset':
                    await reset(username, queue, first_name)
                    continue
                elif api_category == 'refresh_posts':
                    await refresh_posts(body, queue)
                    continue
                elif api_category.endswith('post'):
                    match api_category:
                        case 'create_post': await create_post(body, queue)
                        case 'read_post': await read_post(body, agent, queue)
                        case 'update_post': await update_post(body, queue)
                        case 'delete_post': await delete_post(body, queue)
                    continue
                elif api_category.endswith('note'):
                    match api_category:
                        case 'create_note': await create_note(body, queue)
                        case 'update_note': await update_note(body, queue)
                        case 'delete_note': await delete_note(body, queue)
                    continue

                user_text = body.get('text', '') or body.get('currentMessage', '')
                dax = body.get('dax')
                payload = body.get('payload') or {}
                try:
                    result = await asyncio.to_thread(agent.take_turn, user_text, dax, payload)
                    frame = result.get('frame') or {}
                    if frame.get('origin') == 'create' and (frame.get('data') or {}).get('status') == 'note':
                        all_items = PostService().list_preview().get('items', [])
                        if all_items:
                            note_frame = {'block_type': 'grid', 'panel': 'top', 'origin': 'welcome'}
                            note_frame['data'] = {'items': all_items}
                            note_panel = {'message': '', 'raw_utterance': '', 'actions': [], 'frame': note_frame}
                            await queue.put(note_panel)
                    await queue.put(result)
                except Exception as turn_error:
                    print(f'Turn error: {turn_error}\n{traceback.format_exc()}')
                    await queue.put({'message': _ERROR_MESSAGE})

            except WebSocketDisconnect:
                break
            except asyncio.CancelledError:
                break
            except Exception as error:
                print(f'Unexpected WS error: {error}\n{traceback.format_exc()}')
                try:
                    await queue.put({'message': _ERROR_MESSAGE})
                except Exception:
                    pass
                break

        sender_task.cancel()

    finally:
        if username:
            websocket_connections.pop(username, None)
            cleanup_agent(username, 'websocket')
