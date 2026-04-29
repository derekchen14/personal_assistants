from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from backend.utilities.services import ToolService, split_sentences, join_sentences, resolve_snip_index

_PLACEHOLDER_SECTIONS = [
    ['Introduction', 'Body', 'Conclusion'],
    ['What is it', 'Why it matters', 'How to use it'],
    ['Red', 'White', 'Blue'],
    ['Past', 'Present', 'Future'],
    ['Problem', 'Solution', 'Impact'],
    ['The Good', 'The Bad', 'The Ugly'],
    ['Setup', 'Walkthrough', 'Wrap-up'],
    ['Hook', 'Core Idea', 'Call to Action'],
    ['Context', 'Analysis', 'Takeaway'],
    ['Before', 'During', 'After'],
    ['Observation', 'Hypothesis', 'Evidence'],
    ['Who', 'What', 'Why'],
    ['Myth', 'Reality', 'Lesson'],
    ['Question', 'Exploration', 'Answer'],
    ['Foundation', 'Framework', 'Application'],
    ['Origin', 'Evolution', 'Future'],
]

_VALID_METADATA_KEYS = {'title', 'category', 'tags', 'color', 'status', 'sections'}


class PostService(ToolService):

    def find_posts(self, query:str|None=None, tags:list|None=None,
                   status:str='all', limit:int=4) -> dict:
        entries = self._load_metadata()
        results = []
        query = (query or '').lower()

        for entry in entries:
            snippet = None
            if status != 'all' and entry.get('status') != status:
                continue
            if tags:
                entry_tags = [tag.lower() for tag in entry.get('tags', [])]
                if not any(tag.lower() in entry_tags for tag in tags):
                    continue
            if query:
                searchable = ' '.join([
                    entry.get('title', ''),
                    entry.get('category', '') or '',
                    ' '.join(entry.get('tags', [])),
                ]).lower()
                if query not in searchable:
                    content = self._read_content(entry.get('filename', ''))
                    pos = content.lower().find(query)
                    if pos == -1:
                        continue
                    start = max(0, pos - 60)
                    end = min(len(content), pos + len(query) + 60)
                    snippet = '...' + content[start:end].strip() + '...'

            item = {
                'post_id': entry['post_id'],
                'title': entry['title'],
                'status': entry.get('status'),
                'updated_at': entry.get('updated_at'),
                'preview_snippet': snippet or entry.get('preview', '')[:120],
            }
            results.append(item)
            if len(results) >= limit:
                break

        return self._success(items=results, count=len(results))

    def search_notes(self, query:str|None=None, limit:int=8) -> dict:
        entries = self._load_metadata()
        results = []
        query = (query or '').lower()

        for ent in entries:
            if ent.get('status') != 'note':
                continue
            content = self._read_content(ent.get('filename', ''))
            if query and query not in content.lower() and query not in ent.get('title', '').lower():
                continue
            results.append({
                'post_id': ent['post_id'],
                'updated_at': ent.get('updated_at'),
                'note_content': content[:300],
            })
            if len(results) >= limit:
                break

        return self._success(items=results, count=len(results))

    def get_title(self, post_id:str) -> str | None:
        entries = self._load_metadata()
        ent = self._find_entry(entries, post_id)
        return ent['title'] if ent else None

    def read_metadata(self, post_id:str, include_outline:bool=False,
                      include_preview:bool=False) -> dict:
        ent, _ = self._require_entry(post_id)
        content = self._read_content(ent['filename'])
        sections = self._extract_sections(content)

        section_summaries = [
            {
                'sec_id': sec['sec_id'],
                'title': sec['title'],
                'sentence_count': len(split_sentences('\n'.join(sec['lines']))),
            }
            for sec in sections
        ]

        result = {
            'title': ent['title'],
            'status': ent.get('status'),
            'category': ent.get('category'),
            'tags': ent.get('tags', []),
            'color': ent.get('color', ''),
            'created_at': ent.get('created_at'),
            'updated_at': ent.get('updated_at'),
            'section_ids': [sec['sec_id'] for sec in sections],
            'sections': section_summaries,
        }

        if include_outline:
            result['outline'] = content

        if include_preview:
            preview = {}
            for sec, summary in zip(sections, section_summaries):
                body_lines = [line for line in sec['lines'] if line.strip()]
                preview[sec['sec_id']] = {
                    'section_title': sec['title'],
                    'first_3_lines': body_lines[:3],
                    'sentence_count': summary['sentence_count'],
                }
            result['preview'] = preview

        return self._success(**result)

    def read_section(self, post_id:str, sec_id:str,
                     snip_id:int|tuple|list|None=None,
                     include_sentence_ids:bool=False) -> dict:
        entry, _ = self._require_entry(post_id)
        content = self._read_content(entry['filename'])
        section = self._resolve_section(content, sec_id)
        if not section:
            return self._error('not_found', f'Section not found: {sec_id}')

        raw = '\n'.join(section['lines']).strip()

        # Display path — no slicing needed, hand back the raw section body
        # exactly as it sits on disk. Splitting + rejoining here would only
        # shuffle newlines around without changing anything semantic.
        if snip_id is None and not include_sentence_ids:
            return self._success(
                sec_id=section['sec_id'],
                title=section['title'],
                content=raw,
                sentence_count=len(split_sentences(raw)),
            )

        # Snip-indexed path — split so the caller can slice by snip_id.
        sentences = split_sentences(raw)
        if snip_id is None:
            selected, start_idx = sentences, 0
        elif isinstance(snip_id, int):
            idx = resolve_snip_index(snip_id, len(sentences))
            selected = [sentences[idx]] if 0 <= idx < len(sentences) else []
            start_idx = idx if 0 <= idx < len(sentences) else 0
        else:
            start, end = int(snip_id[0]), int(snip_id[1])
            selected = sentences[start:end]
            start_idx = start

        if include_sentence_ids:
            rendered = '\n'.join(
                f'[{start_idx + offset}] {text}'
                for offset, text in enumerate(selected)
            )
        else:
            rendered = join_sentences(selected)

        return self._success(
            sec_id=section['sec_id'],
            title=section['title'],
            content=rendered,
            sentence_count=len(sentences),
        )

    def create_post(self, title:str, type:str='draft',
                    topic:str|None=None, sections:list|None=None,
                    post_id:str|None=None) -> dict:
        entries = self._load_metadata()
        post_id = post_id or str(uuid.uuid4())[:8]
        status = type if type in ('draft', 'note') else 'draft'
        now = self._now()

        if status == 'note':
            body = topic or ''
            if len(body) > 2048:
                return self._error('validation', 'Note exceeds 2048 character limit.')
            slug = self._derive_note_slug(body) if body else post_id
            filename = self._unique_note_filename(slug, entries)
            (self._content_dir / 'notes').mkdir(parents=True, exist_ok=True)
            (self._content_dir / filename).write_text(body, encoding='utf-8')
            entry = {
                'post_id': post_id, 'title': '', 'status': 'note',
                'category': None, 'created_at': now, 'updated_at': now,
                'preview': self._compute_preview(body),
                'word_count': len(re.sub(r'<[^>]+>', '', body).split()),
                'filename': filename,
            }
            entries.append(entry)
            self._save_metadata(entries)
            return self._success(
                post_id=post_id, title='', status='note',
                created_at=now, updated_at=now, section_ids=[],
            )

        if not title:
            nums = []
            for ent in entries:
                draft_title = ent.get('title', '')
                if draft_title.startswith('Untitled-'):
                    try:
                        nums.append(int(draft_title[9:]))
                    except ValueError:
                        pass
            title = f'Untitled-{max(nums, default=0) + 1:03d}'

        slug = self._slugify(title) + '.md'
        filename = f'drafts/{slug}'
        (self._content_dir / 'drafts').mkdir(parents=True, exist_ok=True)
        filepath = self._content_dir / filename
        if filepath.exists():
            return self._error('duplicate', (
                f'A file already exists at "{filename}". '
                f'Ask the user if they would like to keep the existing file or override it.'
            ))

        if sections:
            sec_titles = sections
        else:
            idx = len(entries) % len(_PLACEHOLDER_SECTIONS)
            sec_titles = _PLACEHOLDER_SECTIONS[idx]

        body_parts = []
        for sec_title in sec_titles:
            body_parts.append(f'## {sec_title}')
            body_parts.append('')
        body = '\n'.join(body_parts)

        self._write_content(filename, {'title': title}, body)

        section_ids = [self._slugify(sec) for sec in sec_titles]
        entry = {
            'post_id': post_id, 'title': title, 'status': 'draft',
            'category': None, 'tags': [], 'color': '',
            'created_at': now, 'updated_at': now,
            'preview': self._compute_preview(body),
            'word_count': len(re.sub(r'<[^>]+>', '', body).split()),
            'filename': filename,
        }
        entries.append(entry)
        self._save_metadata(entries)

        return self._success(
            post_id=post_id, title=title, status='draft',
            created_at=now, updated_at=now, section_ids=section_ids,
        )

    def update_post(self, post_id:str, updates:dict) -> dict:
        ent, entries = self._require_entry(post_id)
        file_content = self._read_content(ent['filename'])

        invalid_keys = set(updates.keys()) - _VALID_METADATA_KEYS
        if invalid_keys:
            return self._error('validation',
                f'Invalid metadata keys: {invalid_keys}. Use content tools for content changes.')

        section_headers = updates.pop('sections', [])
        sections = self._extract_sections(file_content)
        if len(section_headers) == len(sections):
            for sec, new_header in zip(sections, section_headers):
                if sec['title'] != new_header:
                    sec['title'] = new_header
                    sec['sec_id'] = self._slugify(new_header)
            self._save_section_content(ent, sections)
        elif len(section_headers) > 0:
            mismatch_length = f'sections list has {len(section_headers)} entries but the post has {len(sections)}  sections'
            return self._error('validation', mismatch_length)

        for key in ('title', 'category', 'tags', 'color'):
            if key in updates:
                ent[key] = updates[key]

        new_status = updates.get('status')
        if new_status and new_status != ent.get('status'):
            old_path = self._content_dir / ent['filename']
            slug = Path(ent['filename']).name
            if new_status == 'published':
                new_filename = f'posts/{slug}'
            elif new_status == 'note':
                new_filename = f'notes/{slug}'
            else:
                new_filename = f'drafts/{slug}'
            new_path = self._content_dir / new_filename
            new_path.parent.mkdir(parents=True, exist_ok=True)
            if old_path.exists():
                old_path.rename(new_path)
            ent['filename'] = new_filename
            ent['status'] = new_status

        ent['updated_at'] = self._now()
        self._save_metadata(entries)

        return self._success(
            post_id=ent['post_id'], title=ent['title'], status=ent.get('status'),
            category=ent.get('category'), tags=ent.get('tags', []),
            color=ent.get('color', ''), created_at=ent.get('created_at'),
            updated_at=ent['updated_at'],
        )

    def delete_post(self, post_id:str) -> dict:
        entries = self._load_metadata()
        ent = next((e for e in entries if e['post_id'] == post_id), None)
        if ent is None:
            return self._success()
        entries.remove(ent)
        self._save_metadata(entries)
        filepath = self._content_dir / ent['filename']
        if filepath.exists():
            filepath.unlink()
        sdir = self._snapshot_dir(post_id)
        if sdir.exists():
            shutil.rmtree(sdir)
        return self._success()

    def summarize_text(self, post_id:str|None=None, sec_id:str|None=None,
                       note:str|None=None, raw_text:str|None=None) -> dict:
        if raw_text:
            text = raw_text
        elif note:
            text = note
        elif sec_id and post_id:
            ent, _ = self._require_entry(post_id)
            content = self._read_content(ent['filename'])
            sec = self._resolve_section(content, sec_id)
            text = '\n'.join(sec['lines']) if sec else ''
        elif post_id:
            ent, _ = self._require_entry(post_id)
            text = self._read_content(ent['filename'])
        else:
            return self._error('validation', 'Provide at least one of: raw_text, note, sec_id, post_id')

        if not text.strip():
            return self._error('validation', 'No content to summarize.')

        return self._success(
            text_to_summarize=text[:4000],
            word_count=len(text.split()),
            _llm_task='summarize',
        )

    def rollback_post(self, post_id:str, version:int=1) -> dict:
        if version < 1 or version > self.max_snapshots:
            return self._error('validation', f'Version must be 1-{self.max_snapshots}')

        ent, entries = self._require_entry(post_id)
        content = self._read_content(ent['filename'])
        sections = self._extract_sections(content)
        restored_any = False

        for sec in sections:
            snapshot = self._read_snapshot(post_id, sec['sec_id'], version)
            if snapshot is not None:
                sec['lines'] = snapshot.split('\n')
                restored_any = True

        if not restored_any:
            return self._error('not_found', f'No snapshots found at version {version}')

        self._save_section_content(ent, sections)
        self._save_metadata(entries)
        return self._success()

    def list_preview(self, limit:int=100) -> dict:
        entries = self._load_metadata()
        previews = []
        for ent in entries[:limit]:
            preview_item = {
                'post_id': ent['post_id'],
                'title': ent['title'],
                'status': ent.get('status'),
                'category': ent.get('category'),
                'metadata': {'tags': ent.get('tags', []), 'color': ent.get('color')},
                'created_at': ent.get('created_at'),
                'updated_at': ent.get('updated_at'),
                'preview': ent.get('preview', ''),
            }
            if ent.get('status') == 'note':
                preview_item['content'] = self._read_content(ent['filename'])
            previews.append(preview_item)
        return self._success(items=previews, count=len(previews))

    def sync_check(self) -> dict:
        entries = self._load_metadata()
        disk_files: set[str] = set()
        for subdir in ('posts', 'drafts', 'notes'):
            dir_path = self._content_dir / subdir
            for md_file in dir_path.glob('*.md'):
                disk_files.add(f'{subdir}/{md_file.name}')

        meta_files = {ent['filename'] for ent in entries}
        missing = [ent for ent in entries if ent['filename'] not in disk_files]
        new_filenames = disk_files - meta_files

        added = []
        if new_filenames:
            now = self._now()
            for filename in sorted(new_filenames):
                text = (self._content_dir / filename).read_text(encoding='utf-8')
                fm_title, tags, category = self._parse_frontmatter(text)
                title = fm_title or Path(filename).stem.replace('-', ' ').title()
                subdir = filename.split('/')[0]
                status = 'note' if subdir == 'notes' else ('published' if subdir == 'posts' else 'draft')
                body = self._read_content(filename)
                entry = {
                    'post_id': str(uuid.uuid4())[:8],
                    'title': title, 'status': status, 'category': category,
                    'tags': tags, 'color': '', 'created_at': now, 'updated_at': now,
                    'preview': self._compute_preview(body),
                    'word_count': len(re.sub(r'<[^>]+>', '', body).split()),
                    'filename': filename,
                }
                entries.append(entry)
                added.append(entry)
            self._save_metadata(entries)

        return {
            'missing': [{'title': ent.get('title', ent['filename']), 'filename': ent['filename']} for ent in missing],
            'added': [{'title': ent['title'], 'filename': ent['filename']} for ent in added],
        }
