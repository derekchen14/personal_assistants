import asyncio
import traceback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.manager import get_or_create_agent, cleanup_agent, reset_agent
from backend.utilities.services import DatasetService, SavedQueryService, MetricService

chat_router = APIRouter()

websocket_connections: dict = {}
queues: dict = {}


def _get_queue(username: str) -> asyncio.Queue:
    if username not in queues:
        queues[username] = asyncio.Queue()
    return queues[username]


def _build_list_frame(datasets, queries, metrics) -> dict:
    all_items = (
        [{**d, 'entity': 'sheet'} for d in datasets] +
        queries +
        metrics
    )
    return {
        'type': 'list', 'show': True, 'panel': 'top', 'source': 'welcome',
        'data': {'title': 'Dana', 'items': all_items, 'source': 'welcome'},
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

        ds_svc = DatasetService()
        q_svc = SavedQueryService()
        m_svc = MetricService()
        dataset_items = ds_svc.list_datasets().get('result', [])
        welcome_frame = _build_list_frame(dataset_items, q_svc.list_all(), m_svc.list_all())

        await queue.put({
            'message': f"Hey {username}! What data are we exploring today?",
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
                    ds_r = DatasetService()
                    q_r = SavedQueryService()
                    m_r = MetricService()
                    reset_frame = _build_list_frame(
                        ds_r.list_datasets().get('result', []),
                        q_r.list_all(), m_r.list_all(),
                    )
                    await queue.put({
                        'message': f"Hey {username}! What data are we exploring today?",
                        'raw_utterance': '',
                        'actions': [],
                        'interaction': {'type': 'default', 'show': False, 'data': {}},
                        'code_snippet': None,
                        'frame': reset_frame,
                    })
                    continue

                # ── Panel CRUD handlers (all silent: message: '') ──────────────

                select_sheet = body.get('select_sheet')
                if select_sheet:
                    ds_svc2 = DatasetService()
                    datasets = ds_svc2.list_datasets().get('result', [])
                    ds = next((d for d in datasets if d['name'] == select_sheet), None)
                    if ds:
                        card_frame = {
                            'type': 'card', 'show': True, 'panel': 'bottom', 'source': 'select',
                            'data': {
                                'entity': 'sheet',
                                'title': ds['name'],
                                'fields': {
                                    'Rows': ds['row_count'],
                                    'Columns': ', '.join(ds['columns']),
                                },
                            },
                        }
                        await queue.put(_silent(card_frame))
                    continue

                select_query_id = body.get('select_query')
                if select_query_id:
                    entry = SavedQueryService().get(select_query_id)
                    if entry:
                        card_frame = {
                            'type': 'card', 'show': True, 'panel': 'bottom', 'source': 'select',
                            'data': {
                                'entity': 'query',
                                'query_id': entry['query_id'],
                                'title': 'Query',
                                'text': entry['text'],
                            },
                        }
                        await queue.put(_silent(card_frame))
                    continue

                select_metric_id = body.get('select_metric')
                if select_metric_id:
                    entry = MetricService().get(select_metric_id)
                    if entry:
                        card_frame = {
                            'type': 'card', 'show': True, 'panel': 'bottom', 'source': 'select',
                            'data': {
                                'entity': 'metric',
                                'metric_id': entry['metric_id'],
                                'title': entry['name'],
                                'name': entry['name'],
                                'definition': entry.get('definition', ''),
                            },
                        }
                        await queue.put(_silent(card_frame))
                    continue

                if body.get('create_query'):
                    text = body.get('text', '').strip()
                    if text:
                        q_svc2 = SavedQueryService()
                        q_svc2.create(text)
                        m_svc2 = MetricService()
                        ds_svc2 = DatasetService()
                        list_frame = _build_list_frame(
                            ds_svc2.list_datasets().get('result', []),
                            q_svc2.list_all(), m_svc2.list_all(),
                        )
                        await queue.put(_silent(list_frame))
                    continue

                delete_query_id = body.get('delete_query')
                if delete_query_id:
                    q_svc2 = SavedQueryService()
                    q_svc2.delete(delete_query_id)
                    m_svc2 = MetricService()
                    ds_svc2 = DatasetService()
                    list_frame = _build_list_frame(
                        ds_svc2.list_datasets().get('result', []),
                        q_svc2.list_all(), m_svc2.list_all(),
                    )
                    await queue.put(_silent(list_frame))
                    continue

                update_query_id = body.get('update_query')
                if update_query_id:
                    text = body.get('text', '').strip()
                    q_svc2 = SavedQueryService()
                    entry = q_svc2.update(update_query_id, text)
                    m_svc2 = MetricService()
                    ds_svc2 = DatasetService()
                    list_frame = _build_list_frame(
                        ds_svc2.list_datasets().get('result', []),
                        q_svc2.list_all(), m_svc2.list_all(),
                    )
                    await queue.put(_silent(list_frame))
                    if entry:
                        card_frame = {
                            'type': 'card', 'show': True, 'panel': 'bottom', 'source': 'update',
                            'data': {
                                'entity': 'query',
                                'query_id': entry['query_id'],
                                'title': 'Query',
                                'text': entry['text'],
                            },
                        }
                        await queue.put(_silent(card_frame))
                    continue

                if body.get('create_metric'):
                    name = body.get('name', '').strip()
                    definition = body.get('definition', '').strip()
                    if name:
                        m_svc2 = MetricService()
                        entry = m_svc2.create(name, definition)
                        q_svc2 = SavedQueryService()
                        ds_svc2 = DatasetService()
                        list_frame = _build_list_frame(
                            ds_svc2.list_datasets().get('result', []),
                            q_svc2.list_all(), m_svc2.list_all(),
                        )
                        await queue.put(_silent(list_frame))
                        card_frame = {
                            'type': 'card', 'show': True, 'panel': 'bottom', 'source': 'create',
                            'data': {
                                'entity': 'metric',
                                'metric_id': entry['metric_id'],
                                'title': entry['name'],
                                'name': entry['name'],
                                'definition': entry.get('definition', ''),
                            },
                        }
                        await queue.put(_silent(card_frame))
                    continue

                delete_metric_id = body.get('delete_metric')
                if delete_metric_id:
                    m_svc2 = MetricService()
                    m_svc2.delete(delete_metric_id)
                    q_svc2 = SavedQueryService()
                    ds_svc2 = DatasetService()
                    list_frame = _build_list_frame(
                        ds_svc2.list_datasets().get('result', []),
                        q_svc2.list_all(), m_svc2.list_all(),
                    )
                    await queue.put(_silent(list_frame))
                    continue

                update_metric_id = body.get('update_metric')
                if update_metric_id:
                    name = body.get('name', '').strip()
                    definition = body.get('definition', '').strip()
                    m_svc2 = MetricService()
                    entry = m_svc2.update(update_metric_id, name, definition)
                    q_svc2 = SavedQueryService()
                    ds_svc2 = DatasetService()
                    list_frame = _build_list_frame(
                        ds_svc2.list_datasets().get('result', []),
                        q_svc2.list_all(), m_svc2.list_all(),
                    )
                    await queue.put(_silent(list_frame))
                    if entry:
                        card_frame = {
                            'type': 'card', 'show': True, 'panel': 'bottom', 'source': 'update',
                            'data': {
                                'entity': 'metric',
                                'metric_id': entry['metric_id'],
                                'title': entry['name'],
                                'name': entry['name'],
                                'definition': entry.get('definition', ''),
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
