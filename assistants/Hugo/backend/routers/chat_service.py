import asyncio
import re
import traceback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.manager import get_or_create_assistant, cleanup_assistant, reset_assistant
from backend.utilities.services import PostService
from backend.components.task_artifact import TaskArtifact, BuildingBlock

chat_router = APIRouter()
websocket_connections: dict = {}
queues: dict = {}

_ERROR_MESSAGE = "Sorry, I couldn't process that request. Please try rephrasing."

def _get_queue(username:str) -> asyncio.Queue:
    if username not in queues:
        queues[username] = asyncio.Queue()
    return queues[username]


async def reset(username:str, queue:asyncio.Queue, first_name:str=''):
    reset_assistant(username)
    items_r = PostService().list_preview()['items']
    block = BuildingBlock(type='list', data={'title': 'Your Posts', 'items': items_r, 'sectioned': True})
    reset_artifact = TaskArtifact(blocks=[block]).to_dict()
    start_message = f"Hey {first_name}! What are we writing today?"
    reset_msg = {'message': start_message, 'raw_utterance': '', 'actions': [], 'artifact': reset_artifact}
    await queue.put(reset_msg)

async def refresh_posts(body:dict, queue:asyncio.Queue):
    items = PostService().list_preview()['items']
    frame_type = body.get('frame_type', 'list')
    block = BuildingBlock(type=frame_type, data={'title': 'Your Posts', 'items': items, 'sectioned': True})
    refresh_artifact = TaskArtifact(blocks=[block]).to_dict()
    refresh_msg = {'message': '', 'raw_utterance': '', 'actions': [], 'artifact': refresh_artifact}
    await queue.put(refresh_msg)

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
        if result['_success']:
            all_items = post_service.list_preview()['items']
            list_block = BuildingBlock(type=list_type, data={'title': 'Your Posts', 'items': all_items, 'sectioned': True})
            top_msg = {'message': '', 'raw_utterance': '', 'actions': [],
                       'artifact': TaskArtifact(blocks=[list_block]).to_dict()}
            await queue.put(top_msg)
            if post_type == 'draft':
                success_msg = f'Created "{result["title"]}".'
                draft_block = BuildingBlock(type='card', expand=True,
                    data={'post_id': result['post_id'], 'status': result['status'], 'title': title, 'content': ''})
                draft_artifact = TaskArtifact(origin='create', blocks=[draft_block]).to_dict()
                bottom_msg = {'message': success_msg, 'raw_utterance': '', 'actions': [], 'artifact': draft_artifact}
                await queue.put(bottom_msg)
        else:
            await queue.put({'message': result.get('_message', _ERROR_MESSAGE)})
    except Exception as ecp:
        print(f'Create error: {ecp}\n{traceback.format_exc()}')
        await queue.put({'message': _ERROR_MESSAGE})

async def read_post(body:dict, agent, queue:asyncio.Queue):
    post_id = body.get('read_post')
    # The ONE DialogueState — mutate in place, never rebind (world.state always exists).
    agent.world.state.set_active_entity(post=post_id, ver=True)
    if not body.get('view'):
        return
    post_service = PostService()
    # Pull raw outline markdown so bullet/paragraph newlines survive. Going
    # through read_section would route the body through split_sentences,
    # which collapses whitespace (including \n) inside each paragraph.
    meta = post_service.read_metadata(post_id, include_outline=True)
    if not meta['_success']:
        return
    content = re.sub(r'^## _hidden_section_title\n', '', meta['outline'], flags=re.M)
    view_block = BuildingBlock(type='card', data={
        'post_id': post_id, 'title': meta['title'], 'status': meta['status'],
        'content': content, 'section_ids': meta['section_ids']})
    view_msg = {'message': '', 'raw_utterance': '', 'actions': [],
                'artifact': TaskArtifact(blocks=[view_block]).to_dict()}
    await queue.put(view_msg)

async def update_post(body:dict, agent, queue:asyncio.Queue):
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
                # Snapshot pre-edit state so the user can undo their own manual save
                # the same way they undo agent-driven mutations.
                current_sections = post_service._extract_sections(
                    post_service._read_content(ent['filename']))
                if current_sections:
                    post_service.take_snapshot(
                        post_id=post_id, turn_id=agent.world.context.num_utterances,
                        flow_name='manual', summary='manual edit',
                        sections=[{'sec_id': sec['sec_id'], 'lines': sec['lines']}
                                  for sec in current_sections])
                post_service._save_section_content(ent, sections)
                post_service._save_metadata(entries)
        if updates:
            post_service.update_post(post_id, updates)
        # Pull raw outline markdown so bullet/paragraph newlines survive the
        # save→response roundtrip. read_section would route the body through
        # split_sentences and collapse whitespace inside each paragraph.
        meta = post_service.read_metadata(post_id, include_outline=True)
        if meta['_success']:
            content = re.sub(r'^## _hidden_section_title\n', '', meta['outline'], flags=re.M)
            update_block = BuildingBlock(type='card', data={
                'post_id': post_id, 'title': meta['title'],
                'status': meta['status'], 'content': content})
            update_msg = {'message': '', 'raw_utterance': '', 'actions': [],
                          'artifact': TaskArtifact(blocks=[update_block]).to_dict()}
            await queue.put(update_msg)
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
        was_note = pre_meta['_success'] and pre_meta['status'] == 'note'
        list_type = 'grid' if was_note else 'list'
        result = post_service.delete_post(post_id)
        if result['_success']:
            items = post_service.list_preview()['items']
            list_block = BuildingBlock(type=list_type, data={'title': 'Your Posts', 'items': items, 'sectioned': True})
            top_msg = {'message': '', 'raw_utterance': '', 'actions': [],
                       'artifact': TaskArtifact(blocks=[list_block]).to_dict()}
        else:
            top_msg = {'message': result['_message']}
        await queue.put(top_msg)
    except Exception as ecp:
        print(f'Delete error: {ecp}\n{traceback.format_exc()}')
        await queue.put({'message': _ERROR_MESSAGE})


async def _send_grid_refresh(queue:asyncio.Queue):
    items = PostService().list_preview()['items']
    grid_block = BuildingBlock(type='grid', data={'title': 'Your Posts', 'items': items, 'sectioned': True})
    await queue.put({'message': '', 'raw_utterance': '', 'actions': [],
                     'artifact': TaskArtifact(blocks=[grid_block]).to_dict()})


async def create_note(body:dict, queue:asyncio.Queue):
    body_text = body.get('body', '')
    stripped = body_text.strip()
    if len(stripped) < 2 or len(stripped) > 2048:
        await queue.put({'message': 'Note body must be between 2 and 2048 characters.'})
        return
    try:
        result = PostService().create_post('', type='note', topic=body_text)
        if result['_success']:
            await _send_grid_refresh(queue)
        else:
            await queue.put({'message': result['_message']})
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
        if result['_success']:
            await _send_grid_refresh(queue)
        else:
            await queue.put({'message': result['_message']})
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
        agent = get_or_create_assistant(username)
        queue = _get_queue(username)

        post_service = PostService()
        sync = post_service.sync_check()
        post_items = post_service.list_preview()['items']

        welcome_block = BuildingBlock(type='list', data={'title': 'Your Posts', 'items': post_items, 'sectioned': True})
        welcome_artifact = TaskArtifact(blocks=[welcome_block]).to_dict()

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

        welcome_msg = {'message': welcome_message, 'raw_utterance': '', 'actions': [], 'artifact': welcome_artifact}
        await queue.put(welcome_msg)

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
                        case 'update_post': await update_post(body, agent, queue)
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
                    artifact = result.get('artifact') or {}
                    # Phase-2 logging: WS handoff snapshot — what we're about
                    # to put on the wire to the frontend.
                    block_panels = [b.get('panel') for b in (artifact.get('blocks') or [])]
                    print(
                        f'WS-HANDOFF: msg_len={len(result.get("message", ""))} '
                        f'frame_origin={artifact.get("origin")!r} '
                        f'frame_blocks={[b.get("type") for b in (artifact.get("blocks") or [])]} '
                        f'block_panels={block_panels} '
                        f'frame_metadata_keys={sorted((artifact.get("metadata") or {}).keys())}',
                        flush=True,
                    )
                    first_block_data = (artifact.get('blocks') or [{}])[0].get('data') or {}
                    if artifact.get('origin') == 'create' and first_block_data.get('status') == 'note':
                        all_items = PostService().list_preview()['items']
                        note_block = BuildingBlock(type='grid', data={'title': 'Your Posts', 'items': all_items, 'sectioned': True})
                        note_msg = {'message': '', 'raw_utterance': '', 'actions': [],
                                    'artifact': TaskArtifact(blocks=[note_block]).to_dict()}
                        await queue.put(note_msg)
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
            cleanup_assistant(username, 'websocket')
