from __future__ import annotations

from types import MappingProxyType


class DisplayFrame:

    def __init__(self, config: MappingProxyType):
        self.config = config
        self._display_config = config.get('display', {})
        self._page_size = self._display_config.get('page_size', 512)

        self.block_type: str = 'default'
        self.data: dict = {}
        self.source: str | None = None
        self.display_name: str | None = None
        self.code: str | None = None
        self.panel: str = 'bottom'

    _TOP_TYPES = frozenset(('form', 'confirmation', 'toast'))

    def set_frame(self, block_type: str, data: dict,
                  source: str | None = None,
                  display_name: str | None = None,
                  code: str | None = None,
                  panel: str | None = None):
        self.block_type = block_type
        self.data = data
        self.source = source
        self.display_name = display_name
        self.code = code
        if panel is not None:
            self.panel = panel
        else:
            self.panel = 'top' if block_type in self._TOP_TYPES else 'bottom'

    def clear(self):
        self.block_type = 'default'
        self.data = {}
        self.source = None
        self.display_name = None
        self.code = None
        self.panel = 'bottom'

    def has_content(self) -> bool:
        return self.block_type != 'default' and bool(self.data)

    # ── Block composition helpers ────────────────────────────────────

    def compose(self, block_type: str, data: dict) -> dict:
        return {
            'type': block_type,
            'show': block_type != 'default',
            'data': data,
        }

    def card(self, title: str, content: str,
             actions: list | None = None) -> dict:
        return self.compose('card', {
            'title': title, 'content': content,
            'actions': actions or [],
        })

    def listing(self, title: str, items: list) -> dict:
        return self.compose('list', {'title': title, 'items': items})

    def form(self, fields: list[dict],
             submit_label: str = 'Submit') -> dict:
        return self.compose('form', {
            'fields': fields, 'submit_label': submit_label,
        })

    def toast(self, message: str, level: str = 'info') -> dict:
        return self.compose('toast', {'message': message, 'level': level})

    def confirmation(self, prompt: str,
                     confirm_label: str = 'Confirm',
                     cancel_label: str = 'Cancel') -> dict:
        return self.compose('confirmation', {
            'prompt': prompt,
            'confirm_label': confirm_label,
            'cancel_label': cancel_label,
        })

    def to_dict(self) -> dict:
        return {
            'block_type': self.block_type,
            'data': self.data,
            'source': self.source,
            'display_name': self.display_name,
            'code': self.code,
        }
