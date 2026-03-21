from __future__ import annotations

from pathlib import Path


SPECS_DIR = Path(__file__).resolve().parents[4] / '_specs'


class SpecService:
    """Reads spec files from the _specs/ directory."""

    def __init__(self, specs_dir:Path=SPECS_DIR):
        self.specs_dir = specs_dir
        self._index = self._build_index()

    def _build_index(self) -> dict[str, Path]:
        index = {}
        for md_file in self.specs_dir.rglob('*.md'):
            name = md_file.stem
            if name not in index or len(md_file.parts) < len(index[name].parts):
                index[name] = md_file
        return index

    def read(self, spec_name:str, section:str|None=None) -> dict:
        """tool_id: spec_read"""
        path = self._index.get(spec_name)
        if not path or not path.exists():
            return {
                'status': 'error',
                'error_category': 'not_found',
                'message': f"Spec '{spec_name}' not found",
                'retryable': False,
                'metadata': {'tool_id': 'spec_read', 'attempt': 1},
            }
        content = path.read_text(encoding='utf-8')
        if section:
            content = self._extract_section(content, section)
            if content is None:
                return {
                    'status': 'error',
                    'error_category': 'not_found',
                    'message': f"Section '{section}' not found in '{spec_name}'",
                    'retryable': False,
                    'metadata': {'tool_id': 'spec_read', 'attempt': 1},
                }
        return {
            'status': 'success',
            'result': {
                'content': content,
                'spec_name': spec_name,
                'section': section,
            },
            'metadata': {
                'source': str(path.relative_to(self.specs_dir)),
                'char_count': len(content),
            },
        }

    def _extract_section(self, content:str, heading:str) -> str | None:
        lines = content.split('\n')
        capturing = False
        result = []
        target_level = None
        for line in lines:
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()
                if title.lower() == heading.lower():
                    capturing = True
                    target_level = level
                    result.append(line)
                    continue
                elif capturing and level <= target_level:
                    break
            if capturing:
                result.append(line)
        return '\n'.join(result) if result else None
