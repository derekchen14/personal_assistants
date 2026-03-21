from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

_DB_DIR = Path(__file__).resolve().parents[2] / 'database'


class ToolService:

    def __init__(self):
        self._content_dir = _DB_DIR / 'content'
        self._metadata_file = _DB_DIR / 'content' / 'metadata.json'
        self._snap_root = _DB_DIR / '.snapshots'
        self._guides_dir = _DB_DIR / 'guides'
        self.max_snapshots = 4

    def _success(self, **data):
        return {'_success': True, **data}

    def _error(self, error:str, message:str):
        return {'_success': False, '_error': error, '_message': message}

    # -- Metadata I/O -------------------------------------------------------

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load_metadata(self) -> list[dict]:
        if self._metadata_file.exists():
            data = json.loads(self._metadata_file.read_text(encoding='utf-8'))
            return data.get('entries', [])
        return []

    def _save_metadata(self, entries:list[dict]):
        self._content_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_file.write_text(
            json.dumps({'entries': entries}, indent=2, default=str),
            encoding='utf-8',
        )

    @staticmethod
    def _find_entry(entries:list[dict], post_id:str) -> dict | None:
        for ent in entries:
            if ent['post_id'] == post_id:
                return ent
        return None

    # -- Content I/O --------------------------------------------------------

    def _read_content(self, filename:str) -> str:
        """Read .md file, strip YAML frontmatter, return body."""
        filepath = self._content_dir / filename
        if not filepath.exists():
            return ''
        text = filepath.read_text(encoding='utf-8')
        if text.startswith('---'):
            end = text.find('---', 3)
            if end != -1:
                return text[end + 3:].strip()
        return text

    def _write_content(self, filename:str, frontmatter:dict, body:str):
        """Write .md file with YAML frontmatter."""
        filepath = self._content_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        lines = ['---']
        for key, val in frontmatter.items():
            if isinstance(val, list):
                lines.append(f'{key}: [{", ".join(str(item) for item in val)}]')
            else:
                lines.append(f'{key}: "{val}"' if isinstance(val, str) and ' ' in val else f'{key}: {val}')
        lines.append('---')
        lines.append('')
        lines.append(body)
        filepath.write_text('\n'.join(lines), encoding='utf-8')

    @staticmethod
    def _compute_preview(body:str, max_len:int=300) -> str:
        clean = body.replace('<!--more-->', '')
        for para in clean.split('\n\n'):
            stripped = para.strip()
            if not stripped or stripped.startswith('!['):
                continue
            # Skip heading lines within the paragraph
            lines = [line for line in stripped.split('\n')
                     if line.strip() and not line.strip().startswith('#')]
            if not lines:
                continue
            preview = re.sub(r'<[^>]+>', '', '\n'.join(lines))
            if len(preview) > max_len:
                preview = preview[:max_len].rsplit(' ', 1)[0] + '...'
            return preview
        return ''

    # -- Section parsing ----------------------------------------------------

    @staticmethod
    def _extract_sections(content:str) -> list[dict]:
        """Parse content into section dicts with sec_id, title, and body lines."""
        sections = []
        current = None
        for line in content.split('\n'):
            if line.startswith('## '):
                if current:
                    sections.append(current)
                title = line[3:].strip()
                sec_id = ToolService._slugify(title)
                current = {'sec_id': sec_id, 'title': title, 'lines': []}
            elif current is not None:
                current['lines'].append(line)
        if current:
            sections.append(current)
        return sections

    @staticmethod
    def _rebuild_content(sections:list[dict]) -> str:
        """Rebuild markdown content from section dicts."""
        parts = []
        for sec in sections:
            parts.append(f'## {sec["title"]}')
            parts.extend(sec['lines'])
        return '\n'.join(parts)

    @staticmethod
    def _resolve_section(content:str, sec_id:str) -> dict | None:
        for sec in ToolService._extract_sections(content):
            if sec['sec_id'] == sec_id:
                return sec
        return None

    def _save_section_content(self, entry:dict, sections:list[dict]):
        """Write updated sections back to the post file and update metadata."""
        body = self._rebuild_content(sections)
        if entry.get('status') == 'note':
            (self._content_dir / entry['filename']).write_text(body, encoding='utf-8')
        else:
            fm = {'title': entry['title']}
            if entry.get('tags'):
                fm['tags'] = entry['tags']
            if entry.get('color'):
                fm['color'] = entry['color']
            self._write_content(entry['filename'], fm, body)
        entry['preview'] = self._compute_preview(body)
        entry['word_count'] = len(re.sub(r'<[^>]+>', '', body).split())
        entry['updated_at'] = self._now()

    # -- String helpers -----------------------------------------------------

    @staticmethod
    def _slugify(text:str) -> str:
        slug = text.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        return re.sub(r'-+', '-', slug).strip('-')[:80]

    @staticmethod
    def _parse_frontmatter(text:str) -> tuple[str | None, list[str], str | None]:
        title, tags, category = None, [], None
        if not text.startswith('---'):
            return title, tags, category
        end = text.find('---', 3)
        for line in text[3:end].splitlines():
            if line.startswith('title:'):
                title = line[6:].strip().strip('"\'')
            elif line.startswith('tags:'):
                raw = line[5:].strip().strip('[]')
                tags = [tag.strip().strip('"\'') for tag in raw.split(',') if tag.strip()]
            elif line.startswith('category:'):
                category = line[9:].strip().strip('"\'') or None
        return title, tags, category

    @staticmethod
    def _derive_note_slug(body:str) -> str:
        first_line = body.strip().split('\n')[0].lstrip('#').strip()
        tokens = (first_line.split() or body.strip().split())[:4]
        return ToolService._slugify(' '.join(tokens)) if tokens else 'note'

    @staticmethod
    def _unique_note_filename(base_slug:str, entries:list, exclude_id:str|None=None) -> str:
        existing = {ent['filename'] for ent in entries if ent.get('post_id') != exclude_id}
        candidate = f'notes/{base_slug}.md'
        if candidate not in existing:
            return candidate
        num = 1
        while f'notes/{base_slug}-{num}.md' in existing:
            num += 1
        return f'notes/{base_slug}-{num}.md'

    # -- Snapshot helpers ---------------------------------------------------

    def _snapshot_dir(self, post_id:str) -> Path:
        return self._snap_root / post_id

    def _take_snapshot(self, post_id:str, sec_id:str, content_lines:list[str]):
        """Rotate and save a new snapshot for a section."""
        sdir = self._snapshot_dir(post_id) / sec_id
        sdir.mkdir(parents=True, exist_ok=True)

        oldest = sdir / f'snapshot-{self.max_snapshots}.txt'
        if oldest.exists():
            oldest.unlink()
        for idx in range(self.max_snapshots, 1, -1):
            src = sdir / f'snapshot-{idx - 1}.txt'
            dst = sdir / f'snapshot-{idx}.txt'
            if src.exists():
                src.rename(dst)

        (sdir / 'snapshot-1.txt').write_text('\n'.join(content_lines), encoding='utf-8')

    def _read_snapshot(self, post_id:str, sec_id:str, version:int) -> str | None:
        """Read a snapshot. version=0 is current (not stored here), 1-4 are historical."""
        if version < 1 or version > self.max_snapshots:
            return None
        path = self._snapshot_dir(post_id) / sec_id / f'snapshot-{version}.txt'
        if path.exists():
            return path.read_text(encoding='utf-8')
        return None


# ── Re-exports (so pex.py import doesn't change) ─────────────────────

from backend.utilities.post_service import PostService          # noqa: E402
from backend.utilities.content_service import ContentService    # noqa: E402
from backend.utilities.analysis_service import AnalysisService  # noqa: E402
from backend.utilities.platform_service import PlatformService  # noqa: E402
