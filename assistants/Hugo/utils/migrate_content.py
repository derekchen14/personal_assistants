"""One-time migration: populate database/content/ from morethanoneturn blog."""

import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

HUGO_ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = HUGO_ROOT / 'database' / 'content'
POSTS_JSON = HUGO_ROOT / 'database' / 'posts.json'

SOURCE_POSTS = Path(os.path.expanduser(
    '~/Documents/morethanoneturn/_posts'))
SOURCE_DRAFTS = Path(os.path.expanduser(
    '~/Documents/morethanoneturn/_drafts'))


def _new_id() -> str:
    return str(uuid.uuid4())[:8]


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body) from a Jekyll markdown file."""
    if not text.startswith('---'):
        return {}, text
    end = text.find('---', 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip()
    fm = {}
    for line in raw.split('\n'):
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        key = key.strip()
        val = val.strip()
        # Strip quotes
        if (val.startswith('"') and val.endswith('"')) or \
           (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        # Parse tags: [tag1, tag2]
        if key == 'tags' and val.startswith('['):
            val = [t.strip() for t in val.strip('[]').split(',') if t.strip()]
        fm[key] = val
    body = text[end + 3:].strip()
    return fm, body


def _strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text)


def _compute_preview(body: str, max_len: int = 300) -> str:
    # Remove <!--more--> marker
    clean = body.replace('<!--more-->', '')
    # Find first non-empty paragraph
    for para in clean.split('\n\n'):
        stripped = para.strip()
        if not stripped:
            continue
        # Skip headings, images, links-only lines
        if stripped.startswith('#') or stripped.startswith('!['):
            continue
        preview = _strip_html(stripped)
        if len(preview) > max_len:
            preview = preview[:max_len].rsplit(' ', 1)[0] + '...'
        return preview
    return ''


def _word_count(body: str) -> int:
    clean = _strip_html(body)
    return len(clean.split())


def _slug_from_filename(filename: str) -> str:
    """Strip date prefix and extension: 2025-08-07-foo.md -> foo.md"""
    name = Path(filename).stem
    # Strip date prefix (YYYY-MM-DD-)
    m = re.match(r'\d{4}-\d{2}-\d{2}-(.*)', name)
    if m:
        return m.group(1) + '.md'
    return name + '.md'


def _date_from_filename(filename: str) -> str | None:
    m = re.match(r'(\d{4}-\d{2}-\d{2})', filename)
    if m:
        return m.group(1) + 'T00:00:00+00:00'
    return None


def _normalize_tags(fm: dict) -> list[str]:
    """Extract and normalize tags from frontmatter."""
    tags = fm.get('tags', [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',') if t.strip()]
    return tags


def _normalize_date(fm: dict, filename: str) -> str:
    """Extract and normalize date from frontmatter or filename."""
    date_str = fm.get('date')
    if date_str and isinstance(date_str, str):
        if 'T' not in date_str and '+' not in date_str:
            if ' ' in date_str:
                return date_str.replace(' ', 'T') + '+00:00'
            return date_str + 'T00:00:00+00:00'
        return date_str
    return _date_from_filename(filename) or datetime.now(timezone.utc).isoformat()


def _build_entry(post_id: str, fm: dict, body: str, status: str,
                 category: str | None, tags: list[str],
                 date_str: str, filename: str, slug: str) -> dict:
    """Build a metadata entry dict."""
    return {
        'post_id': post_id,
        'title': fm.get('title', slug.replace('-', ' ').replace('.md', '').title()),
        'status': status,
        'category': category,
        'tags': tags,
        'color': fm.get('color', ''),
        'created_at': date_str,
        'updated_at': date_str,
        'preview': _compute_preview(body),
        'word_count': _word_count(body),
        'filename': filename,
    }


def _load_existing_posts() -> dict[str, dict]:
    """Load posts.json, return {source_file: post_dict}."""
    if not POSTS_JSON.exists():
        return {}
    posts = json.loads(POSTS_JSON.read_text(encoding='utf-8'))
    mapping = {}
    for p in posts:
        sf = p.get('metadata', {}).get('source_file', '')
        if sf:
            mapping[sf] = p
    return mapping


def migrate():
    existing = _load_existing_posts()
    entries = []

    # --- Phase A: Posts ---
    posts_dir = CONTENT_DIR / 'posts'
    posts_dir.mkdir(parents=True, exist_ok=True)
    post_files = sorted(SOURCE_POSTS.glob('*.md'))
    print(f'Phase A: {len(post_files)} posts')

    for src in post_files:
        text = src.read_text(encoding='utf-8')
        fm, body = _parse_frontmatter(text)
        slug = _slug_from_filename(src.name)

        matched = existing.get(src.name)
        post_id = matched['post_id'] if matched else _new_id()
        tags = _normalize_tags(fm)
        category = matched['category'] if matched else (tags[0] if tags else None)
        date_str = _normalize_date(fm, src.name)

        shutil.copy2(src, posts_dir / slug)
        entry = _build_entry(post_id, fm, body, 'published', category,
                             tags, date_str, f'posts/{slug}', slug)
        entries.append(entry)
        print(f'  [{post_id}] {entry["title"]}')

    # --- Phase B: Drafts ---
    drafts_dir = CONTENT_DIR / 'drafts'
    drafts_dir.mkdir(parents=True, exist_ok=True)
    draft_files = sorted(
        list(SOURCE_DRAFTS.glob('*.md')) +
        list(SOURCE_DRAFTS.glob('*.markdown'))
    )
    print(f'\nPhase B: {len(draft_files)} drafts')

    for src in draft_files:
        text = src.read_text(encoding='utf-8')
        fm, body = _parse_frontmatter(text)
        slug = _slug_from_filename(src.name)
        if slug.endswith('.markdown'):
            slug = slug.replace('.markdown', '.md')
        if not slug.endswith('.md'):
            slug += '.md'

        post_id = _new_id()
        tags = _normalize_tags(fm)
        category = tags[0] if tags else None
        date_str = _normalize_date(fm, src.name)

        shutil.copy2(src, drafts_dir / slug)
        entry = _build_entry(post_id, fm, body, 'draft', category,
                             tags, date_str, f'drafts/{slug}', slug)
        entries.append(entry)
        print(f'  [{post_id}] {entry["title"]}')

    # --- Phase C: Notes ---
    notes_dir = CONTENT_DIR / 'notes'
    notes_dir.mkdir(parents=True, exist_ok=True)
    print('\nPhase C: 2 notes')

    cookies_body = """---
title: My Favorite Cookies
tags: [food, baking]
---

Here are my favorite cookies, ranked by how likely I am to eat the entire batch in one sitting.

**Levain-Style Chocolate Chip** — Thick, gooey center with a barely-set crumb. The key is under-baking by two minutes and using a mix of bread flour and all-purpose. Brown butter is non-negotiable.

**Tahini Chocolate Chunk** — Nutty, savory, and just sweet enough. Tahini replaces most of the butter, which sounds wrong but creates this incredible fudgy texture. Flaky salt on top.

**Peanut Butter Blossoms** — The classic with the Hershey's kiss pressed in while warm. No one needs to reinvent this. It's perfect.

**Snickerdoodles** — Underrated. The cream of tartar gives them that slight tang that keeps you reaching for another. Roll them aggressively in cinnamon sugar.

**Shortbread** — Three ingredients, zero room for error. Good butter is the entire recipe. I like mine with a pinch of rosemary and lemon zest.

The real secret to great cookies is weighing your flour instead of scooping it. A kitchen scale costs twelve dollars and will change everything.
"""

    energy_body = """---
title: Tips to Maximizing Daily Energy
tags: [health, productivity]
---

A running list of things that actually work for maintaining energy throughout the day, based on years of experimentation.

**Morning sunlight within 30 minutes of waking.** This is the single highest-leverage habit. Ten minutes of direct sunlight resets your circadian clock and suppresses melatonin. Overcast days still count — outdoor light intensity dwarfs indoor lighting by 10-100x.

**Delay caffeine 90 minutes after waking.** Adenosine needs time to clear naturally. Drinking coffee immediately creates an afternoon crash because you're blocking adenosine while levels are still building. Wait, and the caffeine works with your cortisol instead of against it.

**Eat protein first.** A high-protein breakfast (30g+) stabilizes blood sugar for hours. Eggs, Greek yogurt, or a protein shake before any carbs. The research on this is overwhelming and the effect is immediate.

**Cold exposure in the morning.** Even 30 seconds of cold water at the end of a shower triggers a dopamine increase that lasts 3-4 hours. Not comfortable, but the sustained alertness is worth it.

**Move before noon.** Doesn't need to be intense — a 20-minute walk is enough. Exercise increases BDNF and cerebral blood flow. Afternoon workouts are fine for fitness, but morning movement specifically targets cognitive energy.

**Strategic naps: 20 minutes or 90 minutes, nothing in between.** A 20-minute nap catches you before deep sleep. A 90-minute nap completes a full sleep cycle. Anything in between leaves you groggy. Set an alarm.

**Stop eating 3 hours before bed.** Late meals fragment sleep architecture even if you fall asleep fine. Your body can't repair and digest simultaneously. This alone improved my sleep scores more than any supplement.

The common thread: energy isn't about stimulants or willpower. It's about aligning your behavior with your biology.
"""

    for slug, body_text in [('cookies.md', cookies_body), ('energy.md', energy_body)]:
        dest = notes_dir / slug
        dest.write_text(body_text.strip(), encoding='utf-8')

        fm, body = _parse_frontmatter(body_text.strip())
        tags = _normalize_tags(fm)
        now = datetime.now(timezone.utc).isoformat()
        entry = _build_entry(_new_id(), fm, body, 'note',
                             tags[0] if tags else None, tags,
                             now, f'notes/{slug}', slug)
        entries.append(entry)
        print(f'  [{entry["post_id"]}] {entry["title"]}')

    # --- Phase D: Assemble metadata.json ---
    entries.sort(key=lambda e: e.get('created_at', ''), reverse=True)

    metadata_path = CONTENT_DIR / 'metadata.json'
    metadata_path.write_text(
        json.dumps({'entries': entries}, indent=2, default=str),
        encoding='utf-8',
    )

    # Validate
    missing = []
    for e in entries:
        fp = CONTENT_DIR / e['filename']
        if not fp.exists():
            missing.append(e['filename'])

    # Check original post_ids preserved
    preserved = {p['post_id'] for p in _load_existing_posts().values()}
    migrated_ids = {e['post_id'] for e in entries}
    lost = preserved - migrated_ids

    print(f'\n--- Summary ---')
    print(f'Total entries: {len(entries)}')
    print(f'  Published: {sum(1 for e in entries if e["status"] == "published")}')
    print(f'  Drafts:    {sum(1 for e in entries if e["status"] == "draft")}')
    print(f'  Notes:     {sum(1 for e in entries if e["status"] == "note")}')
    if missing:
        print(f'  MISSING FILES: {missing}')
    if lost:
        print(f'  LOST POST_IDS: {lost}')
    else:
        print(f'  All {len(preserved)} original post_ids preserved ✓')
    print(f'Wrote: {metadata_path}')


if __name__ == '__main__':
    migrate()
