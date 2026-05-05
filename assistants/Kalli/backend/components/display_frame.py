VALID_BLOCK_TYPES = frozenset(('card', 'checklist', 'confirmation', 'toast', 'default',
                               'selection', 'list', 'grid', 'compare', 'form'))
_TOP_BLOCK_TYPES = frozenset(('confirmation', 'toast', 'list', 'grid', 'selection', 'checklist', 'form'))

class BuildingBlock:

    def __init__(self, type:str, data:dict, panel:str|None=None, expand:bool=False):
        self.block_type = type
        self.data = data
        if panel is not None:
            self.panel = panel
        elif type in _TOP_BLOCK_TYPES:
            self.panel = 'top'
        else:
            self.panel = 'bottom'
        self.expand = expand

    def to_dict(self) -> dict:
        return {
            'type': self.block_type,
            'data': self.data,
            'panel': self.panel,
            'expand': self.expand,
        }

class DisplayFrame:
    """Multi-block display frame. Five attributes: origin, metadata, blocks, code, thoughts.

    The legacy single-block API (`set_frame(block_type, data, source=, ...)`, `has_content()`,
    `frame.data`, `frame.block_type`) is preserved as a compat shim until callers are migrated."""

    def __init__(self, config=None, origin:str='', metadata:dict={}, blocks:list=[],
                 code:str|None=None, thoughts:str=''):
        # `config` accepted positionally for legacy `DisplayFrame(self.config)` callers; ignored.
        self.origin = origin
        self.metadata = dict(metadata)
        self.blocks = list(blocks)
        self.code = code
        self.thoughts = thoughts

    def set_frame(self, *args, **kwargs):
        # Legacy: set_frame(block_type, data, source=, display_name=, code=, panel=)
        if args and isinstance(args[0], str) and (len(args) >= 2 or 'data' in kwargs):
            block_type = args[0]
            data = args[1] if len(args) >= 2 else kwargs.pop('data', {})
            source = kwargs.pop('source', None)
            display_name = kwargs.pop('display_name', None)
            code = kwargs.pop('code', None)
            panel = kwargs.pop('panel', None)
            block = {'type': block_type, 'data': data}
            if panel is not None:
                block['panel'] = panel
            self.add_block(block)
            if source:
                self.origin = source
                self.metadata['source'] = source
            if display_name:
                self.metadata['display_name'] = display_name
            if code:
                self.code = code
            return
        # New: set_frame(origin=, blocks=, new_data=)
        origin = kwargs.get('origin', args[0] if args else '')
        blocks = kwargs.get('blocks', args[1] if len(args) > 1 else [])
        new_data = kwargs.get('new_data', args[2] if len(args) > 2 else {})
        if len(origin) > 0:
            self.origin = origin
        for new_block in blocks:
            self.add_block(new_block)
        self.metadata.update(new_data)

    def add_block(self, block_data:dict):
        self.blocks.append(BuildingBlock(**block_data))

    def clear(self):
        self.origin = ''
        self.blocks = []
        self.metadata = {}
        self.code = None
        self.thoughts = ''

    def compose(self, block: str, data: dict) -> dict:
        return {'type': block, 'show': block != 'default', 'data': data}

    def to_dict(self) -> dict:
        frame_dict = {
            'origin': self.origin,
            'blocks': [block.to_dict() for block in self.blocks],
            'metadata': self.metadata,
        }
        if self.code:
            frame_dict['code'] = self.code
        if self.thoughts:
            frame_dict['thoughts'] = self.thoughts
        return frame_dict

    # ── Legacy single-block compat ──────────────────────────────────────

    def has_content(self) -> bool:
        return bool(self.blocks) and any(b.block_type != 'default' or b.data for b in self.blocks)

    @property
    def block_type(self) -> str:
        return self.blocks[-1].block_type if self.blocks else 'default'

    @property
    def data(self) -> dict:
        return self.blocks[-1].data if self.blocks else {}

    @property
    def panel(self) -> str:
        return self.blocks[-1].panel if self.blocks else 'bottom'

    @property
    def source(self) -> str:
        return self.metadata.get('source', '')

    @property
    def display_name(self) -> str:
        return self.metadata.get('display_name', '')
