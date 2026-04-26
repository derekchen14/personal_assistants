from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

_DB_DIR = Path(__file__).resolve().parents[2] / 'database'

_SENTENCE_END = re.compile(r'(?<=[.!?])\s+')
_STRUCTURAL_LINE = re.compile(r'^\s*(#{1,6}\s|[-*]\s|\d+\.\s)')
_HEADING_LINE = re.compile(r'^\s*#{1,6}\s')


class OutlineValidationError(ValueError):
    """Raised when a section write would produce a structurally invalid outline (duplicate
    headings, depth overflow, orphaned bullets, etc.). Caught at the PEX dispatch boundary and
    surfaced as `_error: 'validation'` in the tool result so the skill can retry."""


class PostNotFoundError(LookupError):
    """Raised when a `post_id` does not match any entry in metadata. Caught at the PEX dispatch
    boundary and surfaced as `_error: 'not_found'`."""


def _is_structural(line:str) -> bool:
    """A line is structural if it's a markdown heading, bullet, or numbered item. Structural lines
    must survive round-tripping on their own line — flattening them with surrounding prose would
    mash bullets/headings into a single line."""
    return bool(_STRUCTURAL_LINE.match(line))


def _is_heading(line:str) -> bool:
    return bool(_HEADING_LINE.match(line))


def split_sentences(text:str) -> list[str]:
    """Split a section's text into an ordered list of snips.

    Paragraphs (separated by blank lines) are processed independently. A paragraph containing any
    structural line (heading, bullet, numbered item) is split line-by-line so bullets and
    sub-headings keep their own snip. A pure-prose paragraph yields one snip per sentence (`.`,
    `!`, `?` followed by whitespace). Empty strings are dropped. The resulting list is the unit
    that `snip_id` indexes into."""
    text = text.strip()
    if not text:
        return []
    paragraphs = re.split(r'\n\s*\n', text)
    sentences:list[str] = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        lines = [line for line in para.split('\n') if line.strip()]
        if any(_is_structural(line) for line in lines):
            sentences.extend(line.rstrip() for line in lines)
            continue
        flat = re.sub(r'\s+', ' ', para)
        for part in _SENTENCE_END.split(flat):
            part = part.strip()
            if part:
                sentences.append(part)
    return sentences


def join_sentences(sentences:list[str]) -> str:
    """Rejoin snips into a section body. Structural snips (bullets, headings, numbered items) go
    on their own line; prose sentences are space-joined so they flow as a paragraph. A heading
    following a non-heading gets a blank line before it so adjacent heading+bullet groups are
    visually distinct."""
    if not sentences:
        return ''
    parts = [sentences[0]]
    for snip in sentences[1:]:
        prev = parts[-1]
        if _is_heading(snip) and not _is_heading(prev):
            separator = '\n\n'
        elif _is_structural(snip) or _is_structural(prev):
            separator = '\n'
        else:
            separator = ' '
        parts.append(separator + snip)
    return ''.join(parts)


def resolve_snip_index(snip_id:int, length:int) -> int:
    """Map a single-int snip_id to a concrete 0-based index. -1 means the last."""
    return length - 1 if snip_id == -1 else snip_id


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

    def _require_entry(self, post_id:str) -> tuple[dict, list[dict]]:
        """Load metadata and locate the entry, raising `PostNotFoundError` if missing. Returns
        `(entry, entries)` — write callers mutate both, read-only callers can discard `entries` with `_`."""
        entries = self._load_metadata()
        for ent in entries:
            if ent['post_id'] == post_id:
                return ent, entries
        raise PostNotFoundError(f'Post not found: {post_id}')

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
            # Skip heading lines within the paragraph.
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
        """Rebuild markdown content from section dicts. Guarantees a blank line before every
        non-first H2 heading so newly appended sections don't collide with the prior section's
        last bullet. Idempotent: existing blank-line separators inside a section's lines pass
        through untouched rather than double-up."""
        parts = []
        for idx, sec in enumerate(sections):
            if idx > 0 and parts and parts[-1] != '':
                parts.append('')
            parts.append(f'## {sec["title"]}')
            parts.extend(sec['lines'])
        return '\n'.join(parts)

    @staticmethod
    def _resolve_section(content:str, sec_id:str) -> dict | None:
        for sec in ToolService._extract_sections(content):
            if sec['sec_id'] == sec_id:
                return sec
        return None

    def _save_section_content(self, entry:dict, sections:list[dict]) -> None:
        """Write updated sections back to the post file and update metadata. Validates outline
        structure first; raises `OutlineValidationError` WITHOUT writing if the rebuilt content
        fails any structural check."""
        body = self._rebuild_content(sections)
        self._validate_outline(body)
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

    @staticmethod
    def _validate_outline(content:str) -> None:
        """Structural guards run on every section write so violations can't sneak in regardless
        of which tool produced the content. Raises `OutlineValidationError` listing all
        violations; returns silently when the content is well-formed."""
        errors = []
        h2_titles = []
        h3_titles = []
        has_h2 = False

        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('## ') and not stripped.startswith('### '):
                has_h2 = True
                title = stripped[3:].strip()
                if title in h2_titles:
                    errors.append(f'Duplicate H2: "{title}"')
                h2_titles.append(title)
            elif stripped.startswith('### '):
                if not has_h2:
                    errors.append('H3 without parent H2')
                title = stripped[4:].strip()
                if title in h3_titles:
                    errors.append(f'Duplicate H3: "{title}"')
                h3_titles.append(title)
            elif stripped.startswith('- ') or re.match(r'^\d+\.\s', stripped):
                if not has_h2:
                    errors.append('Bullet point without parent section')
            elif stripped.startswith('  *') or stripped.startswith('  -'):
                pass
            elif stripped.startswith('    '):
                nested = stripped.lstrip()
                if nested.startswith('*') or nested.startswith('-') or re.match(r'^\d+\.', nested):
                    errors.append('Outline exceeds 4 levels deep')
                    break

        if errors:
            raise OutlineValidationError('; '.join(errors))

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
        """Read a snapshot. `version=0` is current (not stored here); 1-4 are historical."""
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
