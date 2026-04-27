import asyncio
import re
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
        welcome_block = {'type': 'list', 'location': 'top', 'data': {'title': 'Your Posts', 'items': items_r}} 
        reset_frame = {'origin': 'welcome', 'panel': 'top', 'blocks': [welcome_block]}
    
    start_message = f"Hey {first_name}! What are we writing today?"
    reset_panel = {'message': start_message, 'raw_utterance': '', 'actions': [], 'frame': reset_frame}
    await queue.put(reset_panel)

async def refresh_posts(body:dict, queue:asyncio.Queue):
    post_service = PostService()
    items = post_service.list_preview().get('items', [])
    frame_type = body.get('frame_type', 'list')
    welcome_block = {'type': frame_type, 'location': 'top', 'data': {'title': 'Your Posts', 'items': items}}
    refresh_frame = {'origin': 'welcome', 'panel': 'top', 'blocks': [welcome_block]}
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
            list_type = 'grid'
        else:
            result = post_service.create_post(title, type=post_type)
            list_type = 'list'
        if result.get('_success'):
            all_items = post_service.list_preview().get('items', [])
            page_block = {'type': list_type, 'location': 'top',
                          'data': {'title': 'Your Posts', 'items': all_items}}
            page_frame = {'origin': 'welcome', 'panel': 'top', 'blocks': [page_block]}
            top_panel = {'message': '', 'raw_utterance': '', 'actions': [], 'frame': page_frame}
            await queue.put(top_panel)
            if post_type == 'draft':
                post_id, status = result.get('post_id', ''), result.get('status', '')
                success_msg = f'Created "{result.get("title", title)}".'
                draft_data = {'post_id': post_id, 'status': status, 'title': title, 'content': ''}
                draft_block = {'type': 'card', 'location': 'bottom', 'data': draft_data}
                draft_frame = {'origin': 'create', 'panel': 'bottom', 'blocks': [draft_block]}
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
        state = DialogueState(intent=None, dax=None, turn_count=0)
        agent.world.insert_state(state)
    state.active_post = post_id
    if not body.get('view'):
        return
    post_service = PostService()
    # Pull raw outline markdown so bullet/paragraph newlines survive. Going
    # through read_section would route the body through split_sentences,
    # which collapses whitespace (including \n) inside each paragraph.
    meta = post_service.read_metadata(post_id, include_outline=True)
    if not meta.get('_success'):
        return
    content = re.sub(r'^## _hidden_section_title\n', '', meta.get('outline', ''), flags=re.M)
    view_data = {'post_id': post_id, 'title': meta.get('title', ''), 'status': meta.get('status', ''),
                 'content': content, 'section_ids': meta.get('section_ids', [])}
    view_block = {'type': 'card', 'location': 'bottom', 'data': view_data}
    view_frame = {'origin': 'view', 'panel': 'bottom', 'blocks': [view_block]}
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
        # Pull raw outline markdown so bullet/paragraph newlines survive the
        # save→response roundtrip. read_section would route the body through
        # split_sentences and collapse whitespace inside each paragraph.
        meta = post_service.read_metadata(post_id, include_outline=True)
        if meta.get('_success'):
            content = re.sub(r'^## _hidden_section_title\n', '', meta.get('outline', ''), flags=re.M)
            update_data = {'post_id': post_id, 'title': meta.get('title', ''),
                           'status': meta.get('status', ''), 'content': content}
            update_block = {'type': 'card', 'location': 'bottom', 'data': update_data}
            update_frame = {'origin': 'update', 'panel': 'bottom', 'blocks': [update_block]}
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
        list_type = 'grid' if was_note else 'list'
        result = post_service.delete_post(post_id)
        if result.get('_success'):
            items = post_service.list_preview().get('items', [])
            page_block = {'type': list_type, 'location': 'top', 'data': {'title': 'Your Posts', 'items': items}}
            page_frame = {'origin': 'welcome', 'panel': 'top', 'blocks': [page_block]}
            top_panel = {'message': '', 'raw_utterance': '', 'actions': [], 'frame': page_frame}
        else:
            top_panel = {'message': result.get('_message', _ERROR_MESSAGE)}
        await queue.put(top_panel)
    except Exception as ecp:
        print(f'Delete error: {ecp}\n{traceback.format_exc()}')
        await queue.put({'message': _ERROR_MESSAGE})


async def _send_grid_refresh(queue:asyncio.Queue):
    items = PostService().list_preview().get('items', [])
    grid_block = {'type': 'grid', 'location': 'top', 'data': {'title': 'Your Posts', 'items': items}}
    frame = {'origin': 'welcome', 'panel': 'top', 'blocks': [grid_block]}
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

        welcome_block = {'type': 'list', 'location': 'top', 'data': {'title': 'Your Posts', 'items': post_items}}
        welcome_frame = {'origin': 'welcome', 'panel': 'top', 'blocks': [welcome_block]} if post_items else None

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
                    # Phase-2 logging: WS handoff snapshot — what we're about
                    # to put on the wire to the frontend.
                    print(
                        f'WS-HANDOFF: msg_len={len(result.get("message", ""))} '
                        f'panel={result.get("panel")!r} '
                        f'frame_origin={frame.get("origin")!r} '
                        f'frame_blocks={[b.get("type") for b in (frame.get("blocks") or [])]} '
                        f'frame_metadata_keys={sorted((frame.get("metadata") or {}).keys())}',
                        flush=True,
                    )
                    first_block_data = (frame.get('blocks') or [{}])[0].get('data') or {}
                    if frame.get('origin') == 'create' and first_block_data.get('status') == 'note':
                        all_items = PostService().list_preview().get('items', [])
                        if all_items:
                            note_block = {'type': 'grid', 'location': 'top', 'data': {'items': all_items}}
                            note_frame = {'origin': 'welcome', 'panel': 'top', 'blocks': [note_block]}
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
