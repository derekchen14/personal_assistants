from __future__ import annotations

import io
import logging
from io import BytesIO, StringIO
from types import MappingProxyType
from uuid import uuid4

from schemas.config import load_config
from backend.components.world import World
from backend.components.prompt_engineer import PromptEngineer
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.memory_manager import MemoryManager
from backend.modules.nlu import NLU
from backend.modules.pex import PEX
from backend.modules.res import RES

log = logging.getLogger(__name__)

_MAX_KEEP_GOING = 5


class Agent:

    def __init__(self, username: str = 'user'):
        self.username = username
        self.config = load_config()
        self.conversation_id: str = str(uuid4())

        self.world = World(self.config)
        self.engineer = PromptEngineer(self.config)
        self.ambiguity = AmbiguityHandler(self.config, self.engineer)
        self.memory = MemoryManager(self.config)

        self.nlu = NLU(self.config, self.ambiguity, self.engineer, self.world)
        self.pex = PEX(self.config, self.ambiguity, self.engineer, self.memory, self.world)
        self.res = RES(self.config, self.ambiguity, self.engineer, self.world)

        self.loader = None
        self.data_source_ids: list = []

    # ── Main loop ────────────────────────────────────────────────────

    def take_turn(self, user_text: str) -> dict:
        self.world.context.add_turn('User', user_text, turn_type='utterance')

        if self.ambiguity.present():
            self.ambiguity.resolve()

        state = self.nlu.understand(user_text, self.world.context)
        self.world.context.add_turn(
            'System',
            f'[NLU] intent={state.pred_intent} flow={state.flow_name} '
            f'confidence={state.confidence:.2f}',
            turn_type='meta',
        )

        if not self._self_check(state):
            return self._fallback_response(user_text)

        rounds = 0
        keep_going = True
        last_frame = None

        while keep_going and rounds < _MAX_KEEP_GOING:
            frame, keep_going = self.pex.execute(state, self.world.context)
            last_frame = frame
            rounds += 1
            if keep_going:
                active = self.world.flow_stack.get_active_flow()
                if active:
                    log.info(
                        'keep_going round %d: intent=%s flow=%s',
                        rounds, active.intent, active.name(),
                    )

        response = self.res.respond(state, last_frame)

        agent_text = response.get('message', '')
        self.world.context.add_turn('Agent', agent_text, turn_type='utterance')

        if self.memory.should_summarize(self.world.context.turn_count):
            self._trigger_summarization()

        return self._build_payload(state, response)

    # ── Checks ───────────────────────────────────────────────────────

    def _self_check(self, state) -> bool:
        if state.confidence < 0.1:
            return False
        if not state.flow_name:
            return False
        return True

    def _fallback_response(self, user_text: str) -> dict:
        self.world.context.add_turn(
            'Agent', "I'm not sure I understand. Could you rephrase that?",
            turn_type='utterance',
        )
        return {
            'conversation_id': self.conversation_id,
            'message': "I'm not sure I understand. Could you rephrase that?",
            'display': None,
            'clarification': True,
        }

    def _build_payload(self, state, response: dict) -> dict:
        return {
            'conversation_id': self.conversation_id,
            'message': response.get('message', ''),
            'display': response.get('display'),
            'clarification': response.get('clarification', False),
            'intent': state.pred_intent,
            'flow': state.flow_name,
            'confidence': state.confidence,
        }

    def _trigger_summarization(self):
        log.info('Summarization trigger reached at turn %d',
                 self.world.context.turn_count)

    # ── Lifecycle ────────────────────────────────────────────────────

    def reset(self):
        self.world.reset()
        self.memory.clear_scratchpad()
        self.ambiguity.resolve()
        self.conversation_id = str(uuid4())

    def close(self):
        success, message = self.save_session_state()
        if not success:
            log.warning('Session save warning: %s', message)

    # ── CSV upload (preserved from data-analysis scaffold) ───────────

    def activate_loader(self, extension, multi_tab=False):
        from backend.components.loaders import SpreadsheetLoader, VendorLoader, WarehouseLoader

        if self.loader is None:
            if extension in ['csv', 'tsv', 'xlsx', 'ods']:
                self.loader = SpreadsheetLoader(extension, multi_tab)
            elif extension in ['ga4', 'hubspot', 'amplitude', 'segment',
                               'google', 'drive', 'facebook', 'salesforce']:
                self.loader = VendorLoader(extension)
            elif extension in ['databricks', 'redshift', 'bigquery', 'snowflake']:
                self.loader = WarehouseLoader(extension)

    def initial_pass(self, raw_data, tab_name, index, total):
        file_size = len(raw_data)
        file_size_mb = file_size / (1024 * 1024)

        if file_size_mb > 100:
            return False, False, "File is too large, must be less than 100MB"
        try:
            if self.loader.source in ['csv', 'tsv']:
                decoded_content = raw_data.decode('utf-8')
                self.loader.holding[tab_name] = StringIO(decoded_content)
                is_done = index == total - 1
            elif self.loader.source in ['xlsx', 'ods']:
                self.loader.holding[tab_name] = BytesIO(raw_data)
                is_done = index == total - 1
            else:
                self.loader.holding[tab_name] = raw_data
                is_done = True
        except Exception as exp:
            log.error('initial_pass error: %s', exp)
            return False, True, "File is not a valid CSV table or has invalid characters"

        result = self.loader.get_processed()
        return True, is_done, result

    def multi_tab_pass(self, raw_data, sheet_info):
        import pandas as pd

        file_size = len(raw_data)
        file_size_mb = file_size / (1024 * 1024)
        if file_size_mb > 100:
            return False, [], "File is too large, must be less than 100MB"

        try:
            excel_file = io.BytesIO(raw_data)
            xls = pd.ExcelFile(excel_file)
            for sheet_name, tab_name in zip(xls.sheet_names, sheet_info['tableNames']):
                self.loader.holding[tab_name] = pd.read_excel(xls, sheet_name)
        except Exception as exp:
            return False, [], f"Parsing multi-tab file failed: {exp}"

        table_names = self.loader.get_processed()
        return True, table_names, ""

    def upload_data(self, spreadsheet, details=None):
        import pandas as pd

        details = details or {}
        if len(details) > 0:
            existing_sheets = []
            succeeded, output = self.loader.process_details(
                spreadsheet, existing_sheets, details,
            )
            if succeeded:
                for table_name, table_data in output.get('ss_data', {}).items():
                    if hasattr(table_data, 'to_dict'):
                        formatted_data = {
                            'columns': list(table_data.columns),
                            'data': [],
                        }
                        for col in table_data.columns:
                            col_data = table_data[col].ffill().values
                            col_data = [
                                None if pd.isna(v) else v for v in col_data
                            ]
                            formatted_data['data'].append(col_data)
                    else:
                        formatted_data = table_data

                    uploaded_file_id = uuid4()
                    self.data_source_ids.append(uploaded_file_id)

                self.loader = None
                return True, output
            else:
                self.loader = None
                return False, output
        else:
            dir_name = spreadsheet.ssName.strip()
            table_names = spreadsheet.tabNames
            # Domain-specific: register data with memory backend
            self.loader = None
            return True, table_names

    def fetch_tab_data(self, tab_name, row_start, row_end):
        # Domain-specific: fetch from memory database
        return False, []

    def download_data(self, tab_name, export_type):
        import tempfile
        import pandas as pd

        # Domain-specific: download from memory database
        return None

    def delete_data(self, tab_name):
        # Domain-specific: delete from memory database and update world state
        return False, f"Table '{tab_name}' deletion not configured"

    def save_session_state(self):
        if not self.data_source_ids:
            return True, "No data sources to save"

        try:
            # Domain-specific: save table state to persistent storage
            return True, "Successfully saved all tables"
        except Exception as e:
            return False, f"Error saving tables: {e}"
