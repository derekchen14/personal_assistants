from __future__ import annotations

from pathlib import Path

from backend.utilities.services import ToolService, _DB_DIR


class Entity1Service(ToolService):

    def list_all(self) -> dict:
        items = []
        scan_dir = _DB_DIR / 'entity1s'
        if scan_dir.exists():
            for entry in sorted(scan_dir.iterdir()):
                if entry.is_file():
                    items.append({
                        'entity': 'entity1',
                        'entity1_id': entry.stem,
                        'name': entry.stem,
                        'display_name': entry.stem.replace('_', ' ').title(),
                    })
        return self._success(items)

    def select(self, entity1_id:str) -> dict:
        items = self.list_all().get('result', [])
        item = next((ent for ent in items if ent.get('entity1_id') == entity1_id), None)
        if item is None:
            return self._error(f'entity1 not found: {entity1_id}')
        return self._success({
            **item,
            'fields': {
                'ID': entity1_id,
            },
        })
