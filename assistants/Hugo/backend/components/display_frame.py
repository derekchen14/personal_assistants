from types import MappingProxyType

VALID_BLOCK_TYPES = frozenset(('card', 'checklist', 'confirmation', 'toast', 'default', 'selection', 'list', 'compare'))
_TOP_TYPES = frozenset(('confirmation', 'toast'))

class BuildingBlock:

    def __init__(self, block_type:str, data:dict, location:str):
        self.block_type = block_type
        self.data = data
        self.location = location

    def to_dict(self) -> dict:
        block_dict = {
            'type': self.block_type,
            'data': self.data,
            'location': self.location,
        }
        return block_dict

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
        block_type = block_data['type']
        data = block_data['data']

        if 'location' in block_data:
            location = block_data['location']
        elif block_type in _TOP_TYPES:
            location = 'top'
        else:
            location = 'bottom'

        block = BuildingBlock(block_type, data, location)
        self.blocks.append(block)

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
