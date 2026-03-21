"""WebSocket chat endpoint."""

import asyncio
import traceback
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.manager import get_or_create_agent, cleanup_agent, reset_agent
from backend.utilities.services import RequirementService, ToolDefService

_ASSISTANTS_DIR = Path(__file__).resolve().parents[2].parent


def _discover_assistants() -> list[dict]:
    items = []
    for entry in sorted(_ASSISTANTS_DIR.iterdir()):
        if not entry.is_dir() or entry.name == 'Kalli':
            continue
        readme = entry / 'README.md'
        if not readme.exists():
            continue
        lines = readme.read_text(encoding='utf-8').splitlines()
        name = lines[0].lstrip('# ').strip() if lines else entry.name
        items.append({'name': name})
    return items


def _build_list_frame(assistants, requirements, tools) -> dict:
    all_items = (
        [{**a, 'entity': 'assistant'} for a in assistants] +
        requirements +
        tools
    )
    return {
        'type': 'list', 'show': True, 'panel': 'top', 'source': 'welcome',
        'data': {'title': 'Kalli', 'items': all_items, 'source': 'welcome'},
    }


def _silent(frame) -> dict:
    return {
        'message': '',
        'raw_utterance': '',
        'actions': [],
        'interaction': {'type': 'default', 'show': False, 'data': {}},
        'code_snippet': None,
        'frame': frame,
    }


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

        assistants = _discover_assistants()
        req_svc = RequirementService()
        tool_svc = ToolDefService()
        welcome_frame = _build_list_frame(
            assistants, req_svc.list_all(), tool_svc.list_all()
        )

        await queue.put({
            'message': f"Hey {username}! What assistant are we building?",
            'raw_utterance': '',
            'actions': [],
            'interaction': {'type': 'default', 'show': False, 'data': {}},
            'code_snippet': None,
            'frame': welcome_frame,
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

                if body.get('reset'):
                    reset_agent(username)
                    r_svc = RequirementService()
                    t_svc = ToolDefService()
                    reset_frame = _build_list_frame(
                        _discover_assistants(), r_svc.list_all(), t_svc.list_all()
                    )
                    await queue.put({
                        'message': f"Hey {username}! What assistant are we building?",
                        'raw_utterance': '',
                        'actions': [],
                        'interaction': {'type': 'default', 'show': False, 'data': {}},
                        'code_snippet': None,
                        'frame': reset_frame,
                    })
                    continue

                # ── Panel CRUD handlers (all silent: message: '') ──────────────

                select_name = body.get('select_assistant')
                if select_name:
                    assistant_dir = _ASSISTANTS_DIR / select_name
                    readme = assistant_dir / 'README.md'
                    excerpt = ''
                    if readme.exists():
                        lines = readme.read_text(encoding='utf-8').splitlines()
                        content_lines = [l for l in lines[1:] if l.strip()]
                        excerpt = ' '.join(content_lines[:3])
                    card_frame = {
                        'type': 'card', 'show': True, 'panel': 'bottom', 'source': 'select',
                        'data': {
                            'entity': 'assistant',
                            'title': select_name,
                            'fields': {'Name': select_name, 'About': excerpt},
                        },
                    }
                    await queue.put(_silent(card_frame))
                    continue

                select_req_id = body.get('select_requirement')
                if select_req_id:
                    r_svc = RequirementService()
                    entry = r_svc.get(select_req_id)
                    if entry:
                        card_frame = {
                            'type': 'card', 'show': True, 'panel': 'bottom', 'source': 'select',
                            'data': {
                                'entity': 'requirement',
                                'req_id': entry['req_id'],
                                'title': 'Requirement',
                                'text': entry['text'],
                            },
                        }
                        await queue.put(_silent(card_frame))
                    continue

                select_tool_id = body.get('select_tool')
                if select_tool_id:
                    t_svc = ToolDefService()
                    entry = t_svc.get(select_tool_id)
                    if entry:
                        card_frame = {
                            'type': 'card', 'show': True, 'panel': 'bottom', 'source': 'select',
                            'data': {
                                'entity': 'tool',
                                'tool_id': entry['tool_id'],
                                'title': entry['name'],
                                'name': entry['name'],
                                'description': entry.get('description', ''),
                            },
                        }
                        await queue.put(_silent(card_frame))
                    continue

                if body.get('create_requirement'):
                    text = body.get('text', '').strip()
                    if text:
                        r_svc = RequirementService()
                        r_svc.create(text)
                        t_svc = ToolDefService()
                        list_frame = _build_list_frame(
                            _discover_assistants(), r_svc.list_all(), t_svc.list_all()
                        )
                        await queue.put(_silent(list_frame))
                    continue

                delete_req_id = body.get('delete_requirement')
                if delete_req_id:
                    r_svc = RequirementService()
                    r_svc.delete(delete_req_id)
                    t_svc = ToolDefService()
                    list_frame = _build_list_frame(
                        _discover_assistants(), r_svc.list_all(), t_svc.list_all()
                    )
                    await queue.put(_silent(list_frame))
                    continue

                update_req_id = body.get('update_requirement')
                if update_req_id:
                    text = body.get('text', '').strip()
                    r_svc = RequirementService()
                    entry = r_svc.update(update_req_id, text)
                    t_svc = ToolDefService()
                    list_frame = _build_list_frame(
                        _discover_assistants(), r_svc.list_all(), t_svc.list_all()
                    )
                    await queue.put(_silent(list_frame))
                    if entry:
                        card_frame = {
                            'type': 'card', 'show': True, 'panel': 'bottom', 'source': 'update',
                            'data': {
                                'entity': 'requirement',
                                'req_id': entry['req_id'],
                                'title': 'Requirement',
                                'text': entry['text'],
                            },
                        }
                        await queue.put(_silent(card_frame))
                    continue

                if body.get('create_tool'):
                    name = body.get('name', '').strip()
                    description = body.get('description', '').strip()
                    if name:
                        t_svc = ToolDefService()
                        entry = t_svc.create(name, description)
                        r_svc = RequirementService()
                        list_frame = _build_list_frame(
                            _discover_assistants(), r_svc.list_all(), t_svc.list_all()
                        )
                        await queue.put(_silent(list_frame))
                        card_frame = {
                            'type': 'card', 'show': True, 'panel': 'bottom', 'source': 'create',
                            'data': {
                                'entity': 'tool',
                                'tool_id': entry['tool_id'],
                                'title': entry['name'],
                                'name': entry['name'],
                                'description': entry.get('description', ''),
                            },
                        }
                        await queue.put(_silent(card_frame))
                    continue

                delete_tool_id = body.get('delete_tool')
                if delete_tool_id:
                    t_svc = ToolDefService()
                    t_svc.delete(delete_tool_id)
                    r_svc = RequirementService()
                    list_frame = _build_list_frame(
                        _discover_assistants(), r_svc.list_all(), t_svc.list_all()
                    )
                    await queue.put(_silent(list_frame))
                    continue

                update_tool_id = body.get('update_tool')
                if update_tool_id:
                    name = body.get('name', '').strip()
                    description = body.get('description', '').strip()
                    t_svc = ToolDefService()
                    entry = t_svc.update(update_tool_id, name, description)
                    r_svc = RequirementService()
                    list_frame = _build_list_frame(
                        _discover_assistants(), r_svc.list_all(), t_svc.list_all()
                    )
                    await queue.put(_silent(list_frame))
                    if entry:
                        card_frame = {
                            'type': 'card', 'show': True, 'panel': 'bottom', 'source': 'update',
                            'data': {
                                'entity': 'tool',
                                'tool_id': entry['tool_id'],
                                'title': entry['name'],
                                'name': entry['name'],
                                'description': entry.get('description', ''),
                            },
                        }
                        await queue.put(_silent(card_frame))
                    continue

                # ── Agent turn ────────────────────────────────────────────────
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
