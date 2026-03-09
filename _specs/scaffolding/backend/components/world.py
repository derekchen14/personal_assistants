from __future__ import annotations

from types import MappingProxyType

from backend.components.dialogue_state import DialogueState
from backend.components.display_frame import DisplayFrame
from backend.components.flow_stack import FlowStack
from backend.components.context_coordinator import ContextCoordinator


class World:

    def __init__(self, config: MappingProxyType):
        self.config = config
        self.states: list[DialogueState] = []
        self.frames: list[DisplayFrame] = []
        self.flow_stack = FlowStack(config)
        self.context = ContextCoordinator(config)

        self.metadata: dict = {}

    def current_state(self) -> DialogueState | None:
        return self.states[-1] if self.states else None

    def latest_frame(self) -> DisplayFrame | None:
        return self.frames[-1] if self.frames else None

    def insert_state(self, state: DialogueState) -> DialogueState:
        self.states.append(state)
        return state

    def insert_frame(self, frame: DisplayFrame) -> DisplayFrame:
        self.frames.append(frame)
        return frame

    def reset(self):
        self.states.clear()
        self.frames.clear()
        self.flow_stack.clear()
        self.context.reset()

    # ── Type checks (preserved from data-analysis scaffold) ────────

    def initialize_metadata(self, memory_db, api, properties):
        from backend.components.metadata.issues import metadata_map
        from backend.components.metadata.schema import Schema

        for md_name, metadata_class in metadata_map.items():
            self.metadata[md_name] = {}
            for tab_name in self.valid_tables:
                tab_props = properties[tab_name]
                if md_name == 'schema':
                    table = memory_db.tables[tab_name]
                    self.metadata[md_name][tab_name] = metadata_class(
                        table, tab_name, tab_props, self.caution_level, api=api,
                    )
                else:
                    self.metadata[md_name][tab_name] = metadata_class(
                        tab_name, tab_props, self.caution_level, api=api,
                    )

    def update_metadata(self, table, tab_name, shadow, flow):
        from backend.components.metadata.schema import Schema
        from backend.components.metadata.typechecks import TypeCheck

        current_scheme = self.metadata['schema'][tab_name]
        current_props = current_scheme.tab_properties
        revised_props = {}

        source_slot = flow.slots.get('source', None)
        source_columns = []
        if source_slot and len(source_slot.values) > 0:
            source_columns = [
                entity['col'] for entity in source_slot.values
                if entity['tab'] == tab_name
            ]

        for col in table.columns:
            if col in current_props and col not in source_columns:
                revised_props[col] = current_props[col]
            else:
                if flow.flow_type == 'datatype' and flow.properties:
                    new_col_properties = flow.properties
                else:
                    new_col_properties = TypeCheck.build_properties(col, table[col])
                column, col_props = shadow.convert_to_type(
                    tab_name, table[col], new_col_properties,
                )
                table[col] = column
                revised_props[col] = col_props
        self.metadata['schema'][tab_name] = Schema(
            table, tab_name, revised_props, current_scheme.level,
        )

    def construct_metadata(self, table, predicted_props, tab_name, old_names=None):
        from backend.components.metadata.schema import Schema
        from backend.components.metadata.typechecks import TypeCheck

        old_names = old_names or []
        current_props = {}
        for old_tab_name in old_names:
            current_scheme = self.metadata['schema'][old_tab_name]
            old_props = current_scheme.tab_properties
            for col in old_props:
                current_props[col] = old_props[col]

        finalized_props = {}
        for col in table.columns:
            if col in predicted_props:
                finalized_props[col] = predicted_props[col]
            elif col in current_props:
                finalized_props[col] = current_props[col]
            else:
                finalized_props[col] = TypeCheck.build_properties(col, table[col])

        self.metadata['schema'][tab_name] = Schema(
            table, tab_name, finalized_props, 'medium',
        )
        return finalized_props
