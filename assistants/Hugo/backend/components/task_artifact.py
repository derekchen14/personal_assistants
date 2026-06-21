import base64

VALID_BLOCK_TYPES = frozenset(('card', 'checklist', 'confirmation', 'toast', 'default', 'selection', 'list', 'compare'))
_TOP_BLOCK_TYPES = frozenset(('confirmation', 'toast', 'list', 'grid', 'selection', 'checklist'))

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

class Part:
    """A2A v1.0 Part: exactly one of text, raw, url, data is set. Optional metadata extension."""

    def __init__(self, text:str|None=None, raw:bytes|None=None,
                 url:str|None=None, data:dict|None=None, metadata:dict|None=None):
        present = sum(x is not None for x in (text, raw, url, data))
        if present != 1:
            raise ValueError(f"Part requires exactly one of text/raw/url/data; got {present}")
        self.text = text
        self.raw = raw
        self.url = url
        self.data = data
        self.metadata = metadata

    def to_dict(self) -> dict:
        if self.text is not None:
            payload = {'text': self.text}
        elif self.raw is not None:
            payload = {'raw': base64.b64encode(self.raw).decode()}
        elif self.url is not None:
            payload = {'url': self.url}
        else:
            payload = {'data': self.data}
        if self.metadata:
            payload['metadata'] = self.metadata
        return payload

class TaskArtifact:
    """A2A-aligned artifact: origin + list[Part] + visual BuildingBlocks.

    Internal storage is `parts: list[Part]`. The constructor accepts a
    `parts={dict}` shape (wrapped as a single data Part) plus `thoughts`/`code`
    (each wrapped as a text Part tagged via Part.metadata.kind). Consumer-facing
    properties `artifact.thoughts`, `artifact.code`, `artifact.data` unpack from parts."""

    def __init__(self, origin:str='', parts:dict={}, blocks:list=[], code:str|None=None, thoughts:str=''):
        self.origin = origin
        self.parts = []
        self.blocks = list(blocks)
        if parts:
            self._set_data(parts)
        if thoughts:
            self._set_text('thoughts', thoughts)
        if code:
            self._set_text('code', code)

    @property
    def thoughts(self) -> str:
        return self._get_text('thoughts') or ''

    @thoughts.setter
    def thoughts(self, text:str):
        self._set_text('thoughts', text)

    @property
    def code(self) -> str|None:
        return self._get_text('code')

    @code.setter
    def code(self, text:str|None):
        if text is None:
            return
        self._set_text('code', text)

    @property
    def data(self) -> dict:
        return next((p.data for p in self.parts if p.data is not None), {})

    def add_part(self, **kwargs):
        self.parts.append(Part(**kwargs))

    def update_data(self, **kwargs):
        existing = next((p for p in self.parts if p.data is not None), None)
        if existing:
            existing.data.update(kwargs)
        else:
            self.parts.append(Part(data=dict(kwargs)))

    def set_artifact(self, origin:str='', blocks:list=[], new_data:dict={}):
        if len(origin) > 0:
            self.origin = origin
        for new_block in blocks:
            self.add_block(new_block)
        if new_data:
            self._set_data(new_data)

    def add_block(self, block_data:dict):
        self.blocks.append(BuildingBlock(**block_data))

    def clear(self):
        self.origin = ''
        self.blocks = []
        self.parts = []

    def compose(self, block:str, data:dict) -> dict:
        return {'type': block, 'show': block != 'default', 'data': data}

    def to_dict(self) -> dict:
        return {
            'origin': self.origin,
            'parts': [p.to_dict() for p in self.parts],
            'blocks': [b.to_dict() for b in self.blocks],
        }

    def _get_text(self, kind:str) -> str|None:
        for part in self.parts:
            if part.text is not None and (part.metadata or {}).get('kind') == kind:
                return part.text
        return None

    def _set_text(self, kind:str, text:str):
        for part in self.parts:
            if part.text is not None and (part.metadata or {}).get('kind') == kind:
                part.text = text
                return
        self.parts.append(Part(text=text, metadata={'kind': kind}))

    def _set_data(self, data:dict):
        existing = next((p for p in self.parts if p.data is not None), None)
        if existing:
            existing.data.update(data)
        else:
            self.parts.append(Part(data=dict(data)))
