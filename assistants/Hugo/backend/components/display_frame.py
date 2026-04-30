from types import MappingProxyType

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

class DisplayFrame:

    def __init__(self, origin:str='', metadata:dict={}, blocks:list=[], code:str|None=None, thoughts:str=''):
        self.origin = origin
        self.metadata = dict(metadata)
        self.blocks = list(blocks)
        self.code = code
        self.thoughts = thoughts

    def set_frame(self, origin:str='', blocks:list=[], new_data:dict={}):
        if len(origin) > 0:
            self.origin = origin
        for new_block in blocks:
            self.add_block(new_block)
        self.metadata.update(new_data)

    def add_block(self, block_data:dict):
        self.blocks.append(BuildingBlock(**block_data))

    def clear(self):
        self.origin = None
        self.blocks = []
        self.metadata = {}
        self.code = None
        self.thoughts = ''

    def compose(self, block: str, data: dict) -> dict:
        return {
            'type': block,
            'show': block != 'default',
            'data': data,
        }

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
