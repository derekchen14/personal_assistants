from __future__ import annotations

import re
from pathlib import Path

from backend.utilities.services import ToolService


class AnalysisService(ToolService):

    def brainstorm_ideas(self, topic:str|None=None,
                         source_text:str|None=None,
                         existing_ideas:list|None=None) -> dict:
        from backend.utilities.post_service import PostService
        post_svc = PostService()
        items = []

        if topic:
            result = post_svc.find_posts(query=topic, limit=4)
            if result.get('_success'):
                items.extend(result.get('items', []))

            notes = post_svc.search_notes(query=topic, limit=4)
            if notes.get('_success'):
                for note_item in notes.get('items', []):
                    items.append({
                        'post_id': note_item['post_id'],
                        'title': '',
                        'status': 'note',
                        'snippet': note_item.get('note_content', '')[:200],
                    })

        return self._success(
            items=items, count=len(items),
            topic=topic or '',
        )

    def inspect_post(self, post_id:str, metrics:list|None=None) -> dict:
        ent, _ = self._require_entry(post_id)
        content = self._read_content(ent['filename'])
        sections = self._extract_sections(content)
        lines = content.split('\n')

        word_count = len(re.sub(r'<[^>]+>', '', content).split())
        heading_depth = 0
        image_count = 0
        link_count = 0
        empty_sections = []
        para_lengths = []
        current_para = 0

        for line in lines:
            if line.startswith('#'):
                depth = len(line.split()[0]) if line.split() else 0
                heading_depth = max(heading_depth, depth)
            if re.search(r'!\[.*?\]\(.*?\)', line):
                image_count += 1
            if re.search(r'\[.*?\]\(.*?\)', line):
                link_count += 1
            if line.strip():
                current_para += len(line.split())
            else:
                if current_para > 0:
                    para_lengths.append(current_para)
                    current_para = 0
        if current_para > 0:
            para_lengths.append(current_para)

        for sec in sections:
            body = '\n'.join(sec['lines']).strip()
            if not body:
                empty_sections.append(sec['sec_id'])

        avg_para = round(sum(para_lengths) / max(len(para_lengths), 1), 1)
        read_time = max(1, round(word_count / 238))

        return self._success(
            post_id=post_id, word_count=word_count,
            section_count=len(sections), heading_depth=heading_depth,
            image_count=image_count, link_count=link_count,
            avg_paragraph_length=avg_para, estimated_read_time=read_time,
            empty_sections=empty_sections,
        )

    def check_readability(self, content:str) -> dict:
        sentences = re.split(r'[.!?]+', content)
        sentences = [sent.strip() for sent in sentences if sent.strip()]
        sentence_count = len(sentences) or 1

        words = content.split()
        word_count = len(words) or 1

        def syllable_count(word:str) -> int:
            cleaned = word.lower().rstrip('es').rstrip('ed')
            vowels = 'aeiou'
            count = 0
            prev_vowel = False
            for ch in cleaned:
                is_vowel = ch in vowels
                if is_vowel and not prev_vowel:
                    count += 1
                prev_vowel = is_vowel
            return max(count, 1)

        total_syllables = sum(syllable_count(word) for word in words)
        complex_words = sum(1 for word in words if syllable_count(word) >= 3)

        avg_sentence_length = round(word_count / sentence_count, 1)
        avg_word_length = round(sum(len(word) for word in words) / word_count, 1)

        fk = 0.39 * (word_count / sentence_count) + 11.8 * (total_syllables / word_count) - 15.59
        fk = round(max(0, fk), 1)

        fog = 0.4 * ((word_count / sentence_count) + 100 * (complex_words / word_count))
        fog = round(max(0, fog), 1)

        if fk <= 6:
            label = 'easy'
        elif fk <= 10:
            label = 'moderate'
        elif fk <= 14:
            label = 'advanced'
        else:
            label = 'difficult'

        return self._success(
            flesch_kincaid_grade=fk, gunning_fog=fog,
            avg_sentence_length=avg_sentence_length,
            avg_word_length=avg_word_length,
            sentence_count=sentence_count, score_label=label,
        )

    def check_links(self, content:str) -> dict:
        links = []
        image_count = 0

        for idx, line in enumerate(content.split('\n'), 1):
            for match in re.finditer(r'\[([^\]]*)\]\(([^)]+)\)', line):
                is_image = line[match.start() - 1:match.start()] == '!' if match.start() > 0 else False
                link_type = 'image' if is_image else 'inline'
                if is_image:
                    image_count += 1
                links.append({
                    'url': match.group(2), 'text': match.group(1),
                    'line_number': idx, 'type': link_type,
                })
            for match in re.finditer(r'(?<!\()(https?://[^\s)\]]+)', line):
                url = match.group(0)
                if not any(link['url'] == url and link['line_number'] == idx for link in links):
                    links.append({
                        'url': url, 'text': '', 'line_number': idx, 'type': 'bare',
                    })

        return self._success(links=links, count=len(links), image_count=image_count)

    def compare_style(self, post_id:str, reference_ids:list|None=None) -> dict:
        target_metrics = self.inspect_post(post_id)
        if not target_metrics.get('_success'):
            return target_metrics

        entries = self._load_metadata()
        ent = self._find_entry(entries, post_id)
        content = self._read_content(ent['filename']) if ent else ''
        target_readability = self.check_readability(content)

        target = {**target_metrics, **target_readability}

        references = []
        deltas = {}
        for ref_id in (reference_ids or []):
            ref_metrics = self.inspect_post(ref_id)
            if not ref_metrics.get('_success'):
                continue
            ref_ent = self._find_entry(entries, ref_id)
            ref_content = self._read_content(ref_ent['filename']) if ref_ent else ''
            ref_read = self.check_readability(ref_content)
            ref_data = {**ref_metrics, **ref_read, 'post_id': ref_id}
            references.append(ref_data)

            for key in ('word_count', 'section_count', 'flesch_kincaid_grade',
                        'gunning_fog', 'avg_sentence_length'):
                t_val = target.get(key, 0)
                r_val = ref_data.get(key, 0)
                if isinstance(t_val, (int, float)) and isinstance(r_val, (int, float)):
                    deltas[key] = round(t_val - r_val, 2)

        return self._success(
            target=target, references=references, deltas=deltas,
        )

    def editor_review(self, content:str, guide_path:str|None=None) -> dict:
        path = Path(guide_path) if guide_path else self._guides_dir / 'editor_guide.md'
        guide = ''
        if path.exists():
            guide = path.read_text(encoding='utf-8')

        if not guide:
            return self._error('not_found', 'Editor guide not found.')

        return self._success(
            content=content,
            guide=guide,
            content_length=len(content),
            _llm_task='editor_review',
        )

    def explain_action(self, turn_id:str|None=None, flow_name:str|None=None) -> dict:
        return self._success(
            turn_id=turn_id,
            flow_name=flow_name,
            _llm_task='explain_action',
        )

    def analyze_seo(self, post_id:str, target_keyword:str|None=None) -> dict:
        ent, _ = self._require_entry(post_id)
        content = self._read_content(ent['filename'])
        words = content.lower().split()
        word_count = len(words) or 1
        title = ent.get('title', '')

        suggestions = []

        keyword_density = 0.0
        if target_keyword:
            kw = target_keyword.lower()
            kw_count = content.lower().count(kw)
            keyword_density = round(kw_count / word_count * 100, 2)

            if kw not in title.lower():
                suggestions.append('Add target keyword to title')

            heading_has_kw = False
            for line in content.split('\n'):
                if line.startswith('#') and kw in line.lower():
                    heading_has_kw = True
                    break
            if not heading_has_kw:
                suggestions.append('Add target keyword to H2 headings')

            paragraphs = [para.strip() for para in content.split('\n\n') if para.strip() and not para.strip().startswith('#')]
            if paragraphs and kw not in paragraphs[0].lower():
                suggestions.append('Add target keyword to first paragraph')

        title_length = len(title)
        if title_length > 60:
            suggestions.append('Title exceeds 60 characters (SEO optimal)')
        elif title_length < 20:
            suggestions.append('Title too short for SEO')

        heading_keywords = []
        for line in content.split('\n'):
            if line.startswith('## '):
                heading_keywords.append(line[3:].strip())

        has_meta = bool(ent.get('preview'))
        first_para_has_kw = False
        if target_keyword:
            paragraphs = [para.strip() for para in content.split('\n\n') if para.strip() and not para.strip().startswith('#')]
            if paragraphs:
                first_para_has_kw = target_keyword.lower() in paragraphs[0].lower()

        return self._success(
            keyword_density=keyword_density,
            title_length=title_length,
            heading_keywords=heading_keywords,
            has_meta_description=has_meta,
            first_paragraph_has_keyword=first_para_has_kw,
            suggestions=suggestions,
        )
