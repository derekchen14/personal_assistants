"""
WebSocket chat router — canonical template for personal assistants.

Architecture:
  - One WebSocket per user, opened on connect and closed on disconnect.
  - A per-user asyncio.Queue decouples the send path from the receive path.
    This lets the agent's blocking take_turn() run in a thread while the sender
    can push silent CRUD responses without waiting.
  - Username is read from the first JSON message after connect ("intro").
    No JWT — the cookie is managed by the frontend conversation store and
    re-sent as the intro on each reconnect.

Panel CRUD pattern (lessons 7–10):
  Lesson 7 — _build_list_frame:
    Always bundle ALL entity types into one list frame.  The client filters by
    $activePage, so it always has fresh data regardless of which tab is active.
    Never build separate frames per entity type.

  Lesson 8 — _silent:
    All panel CRUD responses have message: '' so no chat bubble appears.
    The user sees only the panel update.

  Lesson 9 — entity tagging:
    Services tag every item with 'entity': 'entity1' etc. in list_all().
    ListBlock uses this tag to filter items by active page.

  Lesson 10 — CRUD → frame routing:
    select  → card frame only (bottom panel)
    delete  → list frame only (top panel refresh)
    create  → list frame + card frame (refresh + open new item)
    update  → list frame + card frame (same as create)

Replace placeholder names:
  entity1  — read-only entity (e.g., 'sheet' in Dana, 'post' in Hugo)
  entity2  — plain-text editable (e.g., 'query' in Dana)
  entity3  — structured editable (e.g., 'metric' in Dana)
  Entity1Service / Entity2Service / Entity3Service — from utilities/services.py
"""

import asyncio
import traceback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.manager import get_or_create_agent, cleanup_agent, reset_agent
from backend.utilities.services import Entity1Service, Entity2Service, Entity3Service
from backend.components.dialogue_state import DialogueState


chat_router = APIRouter()

# Process-global dicts: one entry per connected user.
websocket_connections: dict = {}
queues: dict = {}


# ── Frame helpers ──────────────────────────────────────────────────────────────

def _build_list_frame(e1s: list, e2s: list, e3s: list) -> dict:
    """
    Build the combined list frame sent after any CRUD mutation.

    All three entity lists merge into one 'items' list.  Each item is tagged
    with its 'entity' type (set by the service's list_all()).  ListBlock reads
    $activePage and filters by that entity tag, so the correct tab is always
    shown without extra requests.

    Why merge all types:  if we sent only the mutated entity's list, the other
    tabs would show stale data the next time the user switches tabs.
    """
    return {
        'type': 'list',
        'show': True,
        'panel': 'top',
        'source': 'welcome',
        'data': {
            'title': 'Your Items',  # Domain-specific: rename to match assistant
            'items': e1s + e2s + e3s,
            'source': 'welcome',
        },
    }


def _silent(frame: dict | None) -> dict:
    """
    Wrap a frame in the full response envelope with an empty message.

    Empty message → no chat bubble in the conversation panel.  The user sees
    only the panel update.  Use for ALL panel CRUD responses.  The agent turn
    path (bottom of the receive loop) sets its own message from the LLM.
    """
    return {
        'message': '',
        'raw_utterance': '',
        'actions': [],
        'interaction': {'type': 'default', 'show': False, 'data': {}},
        'code_snippet': None,
        'frame': frame,
    }


def _get_queue(username: str) -> asyncio.Queue:
    """Return or create the send queue for this user."""
    if username not in queues:
        queues[username] = asyncio.Queue()
    return queues[username]


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@chat_router.websocket('/ws')
async def chat(websocket: WebSocket):
    """
    Main WebSocket handler. One connection per user.

    Lifecycle:
      1. Accept + wait for intro message (username).
      2. Load/create agent and services for this user.
      3. Build welcome response with initial list frame and enqueue it.
      4. Start the sender coroutine task (drains queue → socket).
      5. Enter the receive loop: dispatch CRUD or agent-turn messages.
      6. On disconnect (any cause): cancel sender, clean up agent.
    """
    username = None
    await websocket.accept()

    error_message = "Sorry, I couldn't process that. Please try rephrasing."

    try:
        # ── Intro: read username ───────────────────────────────────────────
        # Frontend sends {username: "..."} immediately after connecting.
        # This is simpler than URL params and works with all WS client libs.
        intro = await websocket.receive_json()
        username = intro.get('username', '').strip()
        if not username:
            await websocket.send_json({'error': 'Username required'})
            await websocket.close(code=1008, reason='Username required')
            return

        first_name = username.split()[0]
        agent = get_or_create_agent(username)
        queue = _get_queue(username)

        # ── Load initial data ──────────────────────────────────────────────
        # Services are stateless thin wrappers — creating them per-connection
        # (and again per-request below) is intentional for thread safety.
        all_e1 = Entity1Service().list_all().get('result', [])
        all_e2 = Entity2Service().list_all().get('result', [])
        all_e3 = Entity3Service().list_all().get('result', [])
        has_items = any([all_e1, all_e2, all_e3])
        welcome_frame = _build_list_frame(all_e1, all_e2, all_e3) if has_items else None

        welcome = _silent(welcome_frame)
        welcome['message'] = f"Hey {first_name}! What can I help you with today?"
        await queue.put(welcome)

        # ── Sender task ────────────────────────────────────────────────────
        # Drains the queue in a separate coroutine so the receive loop is never
        # blocked waiting for a send.  This matters when take_turn() runs in a
        # thread and may enqueue results while a CRUD response is in flight.
        async def sender(q: asyncio.Queue):
            while True:
                try:
                    msg = await q.get()
                    await websocket.send_json(msg)
                except (WebSocketDisconnect, asyncio.CancelledError):
                    break
                except Exception as e:
                    print(f'WebSocket send error: {e}')

        sender_task = asyncio.create_task(sender(queue))
        websocket_connections[username] = websocket

        # ── Receive loop ───────────────────────────────────────────────────
        while True:
            try:
                body = await websocket.receive_json()

                # ── reset ──────────────────────────────────────────────────
                # Clears conversation history and re-shows the welcome frame.
                if body.get('reset'):
                    reset_agent(username)
                    e1s = Entity1Service().list_all().get('result', [])
                    e2s = Entity2Service().list_all().get('result', [])
                    e3s = Entity3Service().list_all().get('result', [])
                    has_r = any([e1s, e2s, e3s])
                    resp = _silent(_build_list_frame(e1s, e2s, e3s) if has_r else None)
                    resp['message'] = f"Hey {first_name}! What can I help you with today?"
                    await queue.put(resp)
                    continue

                # ── select_entity1 → card frame (read-only) ────────────────
                # select: find the item and display it in the bottom panel.
                # No mutation → no list refresh needed.
                select_e1_id = body.get('select_entity1')
                if select_e1_id:
                    try:
                        result = Entity1Service().select(select_e1_id)
                        if result.get('status') == 'success':
                            card_frame = {
                                'type': 'card', 'show': True,
                                'panel': 'bottom', 'source': 'select',
                                'data': {**result['result'], 'entity': 'entity1'},
                            }
                            await queue.put(_silent(card_frame))
                    except Exception as e:
                        print(f'select_entity1 error: {e}')
                    continue

                # ── select_entity2 → card frame (editable, plain text) ─────
                select_e2_id = body.get('select_entity2')
                if select_e2_id:
                    try:
                        result = Entity2Service().select(select_e2_id)
                        if result.get('status') == 'success':
                            card_frame = {
                                'type': 'card', 'show': True,
                                'panel': 'bottom', 'source': 'select',
                                'data': {**result['result'], 'entity': 'entity2'},
                            }
                            await queue.put(_silent(card_frame))
                    except Exception as e:
                        print(f'select_entity2 error: {e}')
                    continue

                # ── select_entity3 → card frame (editable, structured) ─────
                select_e3_id = body.get('select_entity3')
                if select_e3_id:
                    try:
                        result = Entity3Service().select(select_e3_id)
                        if result.get('status') == 'success':
                            card_frame = {
                                'type': 'card', 'show': True,
                                'panel': 'bottom', 'source': 'select',
                                'data': {**result['result'], 'entity': 'entity3'},
                            }
                            await queue.put(_silent(card_frame))
                    except Exception as e:
                        print(f'select_entity3 error: {e}')
                    continue

                # ── create_entity2 → list + card ──────────────────────────
                # create: refresh the list AND open the new item in bottom panel.
                if body.get('create_entity2'):
                    text = body.get('text', '')
                    try:
                        svc = Entity2Service()
                        result = svc.create(text)
                        if result.get('status') == 'success':
                            e1s = Entity1Service().list_all().get('result', [])
                            e2s = svc.list_all().get('result', [])
                            e3s = Entity3Service().list_all().get('result', [])
                            await queue.put(_silent(_build_list_frame(e1s, e2s, e3s)))
                            card_frame = {
                                'type': 'card', 'show': True,
                                'panel': 'bottom', 'source': 'create',
                                'data': {**result['result'], 'entity': 'entity2'},
                            }
                            await queue.put(_silent(card_frame))
                        else:
                            await queue.put({'message': result.get('message', error_message)})
                    except Exception as e:
                        print(f'create_entity2 error: {e}\n{traceback.format_exc()}')
                        await queue.put({'message': error_message})
                    continue

                # ── create_entity3 → list + card ──────────────────────────
                if body.get('create_entity3'):
                    name = body.get('name', '')
                    definition = body.get('definition', '')
                    try:
                        svc = Entity3Service()
                        result = svc.create(name, definition)
                        if result.get('status') == 'success':
                            e1s = Entity1Service().list_all().get('result', [])
                            e2s = Entity2Service().list_all().get('result', [])
                            e3s = svc.list_all().get('result', [])
                            await queue.put(_silent(_build_list_frame(e1s, e2s, e3s)))
                            card_frame = {
                                'type': 'card', 'show': True,
                                'panel': 'bottom', 'source': 'create',
                                'data': {**result['result'], 'entity': 'entity3'},
                            }
                            await queue.put(_silent(card_frame))
                        else:
                            await queue.put({'message': result.get('message', error_message)})
                    except Exception as e:
                        print(f'create_entity3 error: {e}\n{traceback.format_exc()}')
                        await queue.put({'message': error_message})
                    continue

                # ── delete_entity2 → list only ────────────────────────────
                # delete: item is gone, so only refresh the list; no card.
                delete_e2_id = body.get('delete_entity2')
                if delete_e2_id:
                    try:
                        svc = Entity2Service()
                        result = svc.delete(delete_e2_id)
                        if result.get('status') == 'success':
                            e1s = Entity1Service().list_all().get('result', [])
                            e2s = svc.list_all().get('result', [])
                            e3s = Entity3Service().list_all().get('result', [])
                            await queue.put(_silent(_build_list_frame(e1s, e2s, e3s)))
                        else:
                            await queue.put({'message': result.get('message', error_message)})
                    except Exception as e:
                        print(f'delete_entity2 error: {e}\n{traceback.format_exc()}')
                        await queue.put({'message': error_message})
                    continue

                # ── delete_entity3 → list only ────────────────────────────
                delete_e3_id = body.get('delete_entity3')
                if delete_e3_id:
                    try:
                        svc = Entity3Service()
                        result = svc.delete(delete_e3_id)
                        if result.get('status') == 'success':
                            e1s = Entity1Service().list_all().get('result', [])
                            e2s = Entity2Service().list_all().get('result', [])
                            e3s = svc.list_all().get('result', [])
                            await queue.put(_silent(_build_list_frame(e1s, e2s, e3s)))
                        else:
                            await queue.put({'message': result.get('message', error_message)})
                    except Exception as e:
                        print(f'delete_entity3 error: {e}\n{traceback.format_exc()}')
                        await queue.put({'message': error_message})
                    continue

                # ── update_entity2 → list + card ──────────────────────────
                # update: refresh list (label may have changed) + re-open card.
                update_e2_id = body.get('update_entity2')
                if update_e2_id:
                    text = body.get('text', '')
                    try:
                        svc = Entity2Service()
                        result = svc.update(update_e2_id, text)
                        if result.get('status') == 'success':
                            e1s = Entity1Service().list_all().get('result', [])
                            e2s = svc.list_all().get('result', [])
                            e3s = Entity3Service().list_all().get('result', [])
                            await queue.put(_silent(_build_list_frame(e1s, e2s, e3s)))
                            card_frame = {
                                'type': 'card', 'show': True,
                                'panel': 'bottom', 'source': 'update',
                                'data': {**result['result'], 'entity': 'entity2'},
                            }
                            await queue.put(_silent(card_frame))
                        else:
                            await queue.put({'message': result.get('message', error_message)})
                    except Exception as e:
                        print(f'update_entity2 error: {e}\n{traceback.format_exc()}')
                        await queue.put({'message': error_message})
                    continue

                # ── update_entity3 → list + card ──────────────────────────
                update_e3_id = body.get('update_entity3')
                if update_e3_id:
                    name = body.get('name', '')
                    definition = body.get('definition', '')
                    try:
                        svc = Entity3Service()
                        result = svc.update(update_e3_id, name, definition)
                        if result.get('status') == 'success':
                            e1s = Entity1Service().list_all().get('result', [])
                            e2s = Entity2Service().list_all().get('result', [])
                            e3s = svc.list_all().get('result', [])
                            await queue.put(_silent(_build_list_frame(e1s, e2s, e3s)))
                            card_frame = {
                                'type': 'card', 'show': True,
                                'panel': 'bottom', 'source': 'update',
                                'data': {**result['result'], 'entity': 'entity3'},
                            }
                            await queue.put(_silent(card_frame))
                        else:
                            await queue.put({'message': result.get('message', error_message)})
                    except Exception as e:
                        print(f'update_entity3 error: {e}\n{traceback.format_exc()}')
                        await queue.put({'message': error_message})
                    continue

                # ── Agent turn (fallback) ──────────────────────────────────
                # Falls through here when no CRUD key matched.  Run the agent
                # in a thread so it doesn't block the event loop.
                user_text = body.get('text', '') or body.get('currentMessage', '')
                dax = body.get('dax')
                payload = body.get('payload') or {}
                try:
                    result = await asyncio.to_thread(agent.take_turn, user_text, dax, payload)
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
        # Always clean up — whether the client disconnected cleanly, timed out,
        # or threw an exception.  cleanup_agent() is idempotent.
        if username:
            websocket_connections.pop(username, None)
            cleanup_agent(username, 'websocket')
