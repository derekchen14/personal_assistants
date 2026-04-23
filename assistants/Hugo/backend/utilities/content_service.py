from __future__ import annotations

import os
import re
from datetime import datetime
from backend.utilities.services import ToolService, split_sentences, join_sentences, resolve_snip_index

class ContentService(ToolService):

    def __init__(self):
        super().__init__()
        self._images_dir = self._content_dir / 'images'

    def generate_outline(self, post_id:str, content:str, sec_id:str|None=None) -> dict:
        """FULL overwrite of an outline. Used by the `outline` flow when
        starting from scratch, and by `refine` when removing sections. For
        targeted single-section edits, use `generate_section`."""
        errors = self._validate_outline(content)
        if errors:
            return self._error('validation', '; '.join(errors))

        entries = self._load_metadata()
        ent = self._find_entry(entries, post_id)
        if not ent:
            return self._error('not_found', f'Post not found: {post_id}')

        if sec_id:
            file_content = self._read_content(ent['filename'])
            sections = self._extract_sections(file_content)
            found = False
            for sec in sections:
                if sec['sec_id'] == sec_id:
                    sec['lines'] = content.split('\n')
                    found = True
                    break
            if not found:
                return self._error('not_found', f'Section not found: {sec_id}')
            self._save_section_content(ent, sections)
        else:
            if ent.get('status') == 'note':
                (self._content_dir / ent['filename']).write_text(content, encoding='utf-8')
            else:
                fm = {'title': ent['title']}
                if ent.get('tags'):
                    fm['tags'] = ent['tags']
                self._write_content(ent['filename'], fm, content)
            ent['preview'] = self._compute_preview(content)
            ent['word_count'] = len(content.split())
            ent['updated_at'] = self._now()

        self._save_metadata(entries)
        return self._success()

    def generate_section(self, post_id:str, sec_id:str, content:str) -> dict:
        """Save a single section. Used by the `refine` flow for targeted edits.

        If `sec_id` matches an existing section, its content is replaced
        wholesale (and the section renamed if the incoming `## Heading`
        differs — `sec_id` is recomputed from the new title). If `sec_id`
        does not match any existing section, the content is appended as
        a new section at the tail of the outline.

        The `content` argument must begin with a `## Heading` line so the
        tool can detect rename intent; bullets follow.
        """
        errors = self._validate_outline(content)
        if errors:
            return self._error('validation', '; '.join(errors))

        entries = self._load_metadata()
        ent = self._find_entry(entries, post_id)
        if not ent:
            return self._error('not_found', f'Post not found: {post_id}')

        incoming = self._extract_sections(content)
        if not incoming:
            return self._error('validation', 'Section content must include a ## heading')
        inc = incoming[0]
        new_slug = self._slugify(inc['title'])

        file_content = self._read_content(ent['filename'])
        sections = self._extract_sections(file_content)

        renamed = False
        found = False
        for sec in sections:
            if sec['sec_id'] == sec_id:
                renamed = (sec['title'] != inc['title'])
                sec['sec_id'] = new_slug
                sec['title'] = inc['title']
                sec['lines'] = inc['lines']
                found = True
                break
        if not found:
            sections.append({'sec_id': new_slug, 'title': inc['title'], 'lines': inc['lines']})

        self._save_section_content(ent, sections)
        self._save_metadata(entries)
        return self._success(section_id=new_slug, renamed=renamed, appended=(not found))

    def _validate_outline(self, content:str) -> list[str]:
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

        return errors

    def convert_to_prose(self, post_id:str, sec_id:str|None=None) -> dict:
        entries = self._load_metadata()
        ent = self._find_entry(entries, post_id)
        if not ent:
            return self._error('not_found', f'Post not found: {post_id}')

        content = self._read_content(ent['filename'])

        if sec_id:
            sec = self._resolve_section(content, sec_id)
            if not sec:
                return self._error('not_found', f'Section not found: {sec_id}')
            converted = self._outline_to_skeleton(sec['lines'])
            sections = self._extract_sections(content)
            for sec_item in sections:
                if sec_item['sec_id'] == sec_id:
                    sec_item['lines'] = converted.split('\n')
                    break
            self._save_section_content(ent, sections)
        else:
            sections = self._extract_sections(content)
            for sec_item in sections:
                converted = self._outline_to_skeleton(sec_item['lines'])
                sec_item['lines'] = converted.split('\n')
            self._save_section_content(ent, sections)

        self._save_metadata(entries)
        return self._success()

    @staticmethod
    def _outline_to_skeleton(lines:list[str]) -> str:
        result = []
        current_subsection = None

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('### '):
                if current_subsection:
                    result.append('')
                current_subsection = stripped[4:].strip()
                result.append(f'### {current_subsection}')
                result.append('')
            elif stripped.startswith('- ') or stripped.startswith('* ') or re.match(r'^\d+\.\s', stripped):
                bullet_text = re.sub(r'^[-*]\s+|^\d+\.\s+', '', stripped)
                result.append(f'{bullet_text}.')
                result.append('')
            elif stripped.startswith('  *') or stripped.startswith('  -'):
                sub_text = stripped.lstrip(' *-').strip()
                result.append(f'  {sub_text}.')
            elif stripped:
                result.append(stripped)
            else:
                result.append('')

        return '\n'.join(result)

    def insert_section(self, post_id:str, sec_id:str,
                       section_title:str, content:str|None=None) -> dict:
        entries = self._load_metadata()
        ent = self._find_entry(entries, post_id)
        if not ent:
            return self._error('not_found', f'Post not found: {post_id}')

        file_content = self._read_content(ent['filename'])
        sections = self._extract_sections(file_content)

        insert_idx = None
        for idx, sec in enumerate(sections):
            if sec['sec_id'] == sec_id:
                insert_idx = idx + 1
                break
        if insert_idx is None:
            return self._error('not_found', f'Section not found: {sec_id}')

        new_sec = {
            'sec_id': self._slugify(section_title),
            'title': section_title,
            'lines': (content or '').split('\n'),
        }
        sections.insert(insert_idx, new_sec)
        self._save_section_content(ent, sections)
        self._save_metadata(entries)
        return self._success()

    def revise_content(self, post_id:str, sec_id:str,
                       content:str, snip_id:int|tuple|list|None=None) -> dict:
        entries = self._load_metadata()
        ent = self._find_entry(entries, post_id)
        if not ent:
            return self._error('not_found', f'Post not found: {post_id}')

        file_content = self._read_content(ent['filename'])
        sections = self._extract_sections(file_content)

        for sec in sections:
            if sec['sec_id'] == sec_id:
                self._take_snapshot(post_id, sec_id, sec['lines'])

                if snip_id is None:
                    sec['lines'] = content.split('\n')
                else:
                    existing_text = '\n'.join(sec['lines'])
                    sentences = split_sentences(existing_text)
                    new_piece = content.strip()
                    if isinstance(snip_id, int):
                        idx = len(sentences) if snip_id == -1 else snip_id
                        sentences.insert(idx, new_piece)
                    else:
                        start, end = int(snip_id[0]), int(snip_id[1])
                        sentences[start:end] = [new_piece]
                    sec['lines'] = join_sentences(sentences).split('\n')

                self._save_section_content(ent, sections)
                self._save_metadata(entries)
                return self._success()

        return self._error('not_found', f'Section not found: {sec_id}')

    def write_text(self, instructions:str, seed_content:str, location:str='append') -> dict:
        word_count = len(seed_content.split())
        if word_count > 2048:
            return self._error('validation',
                f'Seed content too long ({word_count} words). Max 2048.')

        guide_path = self._guides_dir / 'writing_guide.md'
        guide = ''
        if guide_path.exists():
            guide = guide_path.read_text(encoding='utf-8')

        return self._success(
            seed_content=seed_content,
            instructions=instructions,
            location=location,
            writing_guide=guide,
            _llm_task='write_text',
        )

    def remove_content(self, post_id:str, sec_id:str,
                       snip_id:int|tuple|list|None=None) -> dict:
        entries = self._load_metadata()
        ent = self._find_entry(entries, post_id)
        if not ent:
            return self._error('not_found', f'Post not found: {post_id}')

        file_content = self._read_content(ent['filename'])
        sections = self._extract_sections(file_content)

        if snip_id is None:
            for idx, sec in enumerate(sections):
                if sec['sec_id'] == sec_id:
                    self._take_snapshot(post_id, sec_id, sec['lines'])
                    sections.pop(idx)
                    self._save_section_content(ent, sections)
                    self._save_metadata(entries)
                    return self._success()
            return self._error('not_found', f'Section not found: {sec_id}')

        for sec in sections:
            if sec['sec_id'] == sec_id:
                self._take_snapshot(post_id, sec_id, sec['lines'])
                existing_text = '\n'.join(sec['lines'])
                sentences = split_sentences(existing_text)

                if isinstance(snip_id, int):
                    idx = resolve_snip_index(snip_id, len(sentences))
                    if 0 <= idx < len(sentences):
                        sentences.pop(idx)
                else:
                    start, end = int(snip_id[0]), int(snip_id[1])
                    del sentences[start:end]

                new_text = join_sentences(sentences)
                sec['lines'] = new_text.split('\n') if new_text else []
                self._save_section_content(ent, sections)
                self._save_metadata(entries)
                return self._success()

        return self._error('not_found', f'Section not found: {sec_id}')

    def cut_and_paste(self, post_id:str, source_section:str,
                      target_section:str,
                      source_snip_id:int|tuple|list|None=None,
                      target_snip_id:int|None=None) -> dict:
        if source_section == target_section and source_snip_id is None:
            return self._error('validation', 'Cannot move entire section to itself')

        entries = self._load_metadata()
        ent = self._find_entry(entries, post_id)
        if not ent:
            return self._error('not_found', f'Post not found: {post_id}')

        file_content = self._read_content(ent['filename'])
        sections = self._extract_sections(file_content)

        src = None
        tgt = None
        for sec in sections:
            if sec['sec_id'] == source_section:
                src = sec
            if sec['sec_id'] == target_section:
                tgt = sec

        if not src:
            return self._error('not_found', f'Source section not found: {source_section}')
        if not tgt:
            return self._error('not_found', f'Target section not found: {target_section}')

        src_sentences = split_sentences('\n'.join(src['lines']))
        tgt_sentences = split_sentences('\n'.join(tgt['lines']))

        if source_snip_id is None:
            moved = src_sentences[:]
            src_sentences = []
        elif isinstance(source_snip_id, int):
            idx = resolve_snip_index(source_snip_id, len(src_sentences))
            moved = [src_sentences.pop(idx)] if 0 <= idx < len(src_sentences) else []
        else:
            start, end = int(source_snip_id[0]), int(source_snip_id[1])
            moved = src_sentences[start:end]
            del src_sentences[start:end]

        if target_snip_id is None:
            tgt_sentences.extend(moved)
        else:
            idx = len(tgt_sentences) if target_snip_id == -1 else int(target_snip_id)
            for offset, sentence in enumerate(moved):
                tgt_sentences.insert(idx + offset, sentence)

        src['lines'] = join_sentences(src_sentences).split('\n') if src_sentences else []
        tgt['lines'] = join_sentences(tgt_sentences).split('\n') if tgt_sentences else []

        self._save_section_content(ent, sections)
        self._save_metadata(entries)
        return self._success()

    def diff_section(self, post_id:str, source_section:str,
                     target_section:str|None=None, version:int=0) -> dict:
        import difflib

        entries = self._load_metadata()
        ent = self._find_entry(entries, post_id)
        if not ent:
            return self._error('not_found', f'Post not found: {post_id}')

        content = self._read_content(ent['filename'])
        src = self._resolve_section(content, source_section)
        if not src:
            return self._error('not_found', f'Section not found: {source_section}')

        source_lines = src['lines']

        if target_section:
            if target_section == source_section:
                return self._error('validation', 'Source and target sections must differ')
            tgt = self._resolve_section(content, target_section)
            if not tgt:
                return self._error('not_found', f'Section not found: {target_section}')
            target_lines = tgt['lines']
            compare_label = f'section:{target_section}'
        elif version > 0:
            snapshot = self._read_snapshot(post_id, source_section, version)
            if snapshot is None:
                return self._error('not_found', f'No snapshot at version {version}')
            target_lines = snapshot.split('\n')
            compare_label = f'snapshot-{version}'
        else:
            return self._error('validation', 'Provide target_section or version > 0')

        diff = list(difflib.unified_diff(
            target_lines, source_lines,
            fromfile=compare_label, tofile=f'section:{source_section}',
            lineterm='',
        ))

        return self._success(
            source=source_section,
            target=compare_label,
            diff=diff,
            additions=sum(1 for line in diff if line.startswith('+') and not line.startswith('+++')),
            deletions=sum(1 for line in diff if line.startswith('-') and not line.startswith('---')),
        )

    def insert_media(self, prompt:str, style:str|None=None) -> dict:
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            return self._error('auth_error',
                'GOOGLE_API_KEY not set. Cannot generate images.')

        self._images_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        image_path = self._images_dir / f'img_{timestamp}.png'

        return self._success(
            image_path=str(image_path),
            markdown_ref=f'![{prompt}]({image_path.name})',
            prompt=prompt,
            style=style,
            _api_task='generate_image',
        )

    def web_search(self, query:str, limit:int=5) -> dict:
        api_key = os.getenv('TAVILY_API_KEY')
        if not api_key:
            return self._error('auth_error',
                'TAVILY_API_KEY not set. Cannot search the web.')

        try:
            import httpx
            resp = httpx.post(
                'https://api.tavily.com/search',
                json={'api_key': api_key, 'query': query, 'max_results': limit},
                timeout=15.0,
            )
            if resp.status_code != 200:
                return self._error('server_error', f'Tavily API returned {resp.status_code}')
            data = resp.json()
            items = [
                {'title': res.get('title', ''), 'url': res.get('url', ''), 'snippet': res.get('content', '')[:200]}
                for res in data.get('results', [])
            ]
            return self._success(items=items, count=len(items), query=query)
        except ImportError:
            return self._error('server_error', 'httpx not installed.')
        except Exception as exc:
            return self._error('server_error', f'Web search failed: {exc}')
