"""Sync Hugo's database/content/ against the morethanoneturn blog (prod).

Compares posts and drafts between prod (morethanoneturn) and dev (Hugo),
shows discrepancies interactively, and lets the user choose how to resolve each.
"""

import difflib
import json
import os
import re
import shutil
from pathlib import Path

HUGO_ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = HUGO_ROOT / 'database' / 'content'
METADATA_FILE = CONTENT_DIR / 'metadata.json'

PROD_POSTS = Path(os.path.expanduser('~/Documents/morethanoneturn/_posts'))
PROD_DRAFTS = Path(os.path.expanduser('~/Documents/morethanoneturn/_drafts'))

DEV_POSTS = CONTENT_DIR / 'posts'
DEV_DRAFTS = CONTENT_DIR / 'drafts'

DIFF_TRUNCATE = 10


# ── Helpers ──────────────────────────────────────────────────────────

def _slug_from_filename(filename: str) -> str:
    """Strip date prefix and normalize extension: 2025-08-07-foo.md -> foo.md"""
    name = Path(filename).stem
    m = re.match(r'\d{4}-\d{2}-\d{2}-(.*)', name)
    base = m.group(1) if m else name
    return base + '.md'


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
        if (val.startswith('"') and val.endswith('"')) or \
           (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        if key == 'tags' and val.startswith('['):
            val = [t.strip() for t in val.strip('[]').split(',') if t.strip()]
        fm[key] = val
    body = text[end + 3:].strip()
    return fm, body


def _strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text)


def _compute_preview(body: str, max_len: int = 300) -> str:
    clean = body.replace('<!--more-->', '')
    for para in clean.split('\n\n'):
        stripped = para.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('!['):
            continue
        preview = _strip_html(stripped)
        if len(preview) > max_len:
            preview = preview[:max_len].rsplit(' ', 1)[0] + '...'
        return preview
    return ''


def _read_body(filepath: Path) -> str:
    """Read file, strip frontmatter, return body."""
    text = filepath.read_text(encoding='utf-8')
    _, body = _parse_frontmatter(text)
    return body


def _build_slug_map(prod_dir: Path, extensions: list[str]) -> dict[str, Path]:
    """Return {slug: prod_filepath} for all files in prod_dir."""
    mapping = {}
    for ext in extensions:
        for f in prod_dir.glob(f'*{ext}'):
            slug = _slug_from_filename(f.name)
            if slug.endswith('.markdown'):
                slug = slug.replace('.markdown', '.md')
            mapping[slug] = f
    return mapping


def _diff_lines(prod_body: str, dev_body: str) -> list[str]:
    """Compute unified diff lines between prod and dev."""
    prod_lines = prod_body.splitlines(keepends=True)
    dev_lines = dev_body.splitlines(keepends=True)
    return list(difflib.unified_diff(
        prod_lines, dev_lines,
        fromfile='prod', tofile='dev', lineterm='',
    ))


def _count_changed_lines(diff: list[str]) -> int:
    """Count lines that are actual additions/removals (not headers)."""
    return sum(1 for line in diff if line.startswith('+') or line.startswith('-'))


def _show_diff(diff: list[str], slug: str):
    """Display a diff, truncating if large."""
    changed = _count_changed_lines(diff)
    if changed <= DIFF_TRUNCATE:
        for line in diff:
            _print_diff_line(line)
    else:
        shown = 0
        for line in diff:
            if shown >= DIFF_TRUNCATE:
                break
            _print_diff_line(line)
            if line.startswith('+') or line.startswith('-'):
                shown += 1
        remaining = changed - shown
        print(f'  ... and {remaining} more changed lines')


def _print_diff_line(line: str):
    """Print a single diff line with color hints."""
    line = line.rstrip('\n')
    if line.startswith('+++') or line.startswith('---'):
        print(f'  \033[1m{line}\033[0m')
    elif line.startswith('+'):
        print(f'  \033[32m{line}\033[0m')
    elif line.startswith('-'):
        print(f'  \033[31m{line}\033[0m')
    elif line.startswith('@@'):
        print(f'  \033[36m{line}\033[0m')
    else:
        print(f'  {line}')


def _prompt_choice(is_small: bool) -> str:
    """Prompt user for resolution choice. Returns 'p', 'd', or 'e'."""
    if is_small:
        options = '(p)rod / (d)ev / (e)dit'
    else:
        options = '(p)rod / (d)ev'
    while True:
        choice = input(f'  Keep? {options}: ').strip().lower()
        if choice in ('p', 'd'):
            return choice
        if choice == 'e' and is_small:
            return choice
        print(f'  Invalid choice. Enter {options}')


def _edit_and_apply(prod_path: Path, dev_path: Path, prod_body: str):
    """Open an interactive line editor for small diffs."""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.md', delete=False, encoding='utf-8',
    )
    tmp.write(prod_path.read_text(encoding='utf-8'))
    tmp.close()
    tmp_path = Path(tmp.name)

    editor = os.environ.get('EDITOR', 'nano')
    print(f'  Opening {editor}... Save and close to apply.')
    os.system(f'{editor} {tmp_path}')

    edited = tmp_path.read_text(encoding='utf-8')
    tmp_path.unlink()

    # Write to both locations
    prod_path.write_text(edited, encoding='utf-8')
    dev_path.write_text(edited, encoding='utf-8')


def _update_metadata_entry(slug: str, subdir: str, body: str):
    """Update preview and word_count in metadata.json for the given file."""
    if not METADATA_FILE.exists():
        return
    data = json.loads(METADATA_FILE.read_text(encoding='utf-8'))
    filename = f'{subdir}/{slug}'
    for entry in data.get('entries', []):
        if entry.get('filename') == filename:
            entry['preview'] = _compute_preview(body)
            entry['word_count'] = len(_strip_html(body).split())
            break
    METADATA_FILE.write_text(
        json.dumps(data, indent=2, default=str), encoding='utf-8',
    )


# ── Main ─────────────────────────────────────────────────────────────

def sync():
    stats = {
        'posts_checked': 0,
        'drafts_checked': 0,
        'discrepancies': 0,
        'kept_prod': 0,
        'kept_dev': 0,
        'edited': 0,
        'prod_only': 0,
        'dev_only': 0,
    }

    print('=== Checking Posts ===\n')
    _sync_directory(
        PROD_POSTS, DEV_POSTS, 'posts',
        extensions=['*.md'], stats=stats, stat_key='posts_checked',
    )

    print('\n=== Checking Drafts ===\n')
    _sync_directory(
        PROD_DRAFTS, DEV_DRAFTS, 'drafts',
        extensions=['*.md', '*.markdown'], stats=stats, stat_key='drafts_checked',
    )

    # Summary
    print('\n' + '=' * 40)
    print('  SYNC SUMMARY')
    print('=' * 40)
    print(f'  Posts checked:   {stats["posts_checked"]}')
    print(f'  Drafts checked:  {stats["drafts_checked"]}')
    print(f'  Discrepancies:   {stats["discrepancies"]}')
    print(f'    Kept prod:     {stats["kept_prod"]}')
    print(f'    Kept dev:      {stats["kept_dev"]}')
    print(f'    Edited:        {stats["edited"]}')
    print(f'  Prod-only:       {stats["prod_only"]}')
    print(f'  Dev-only:        {stats["dev_only"]}')


def _sync_directory(prod_dir: Path, dev_dir: Path, subdir: str,
                    extensions: list[str], stats: dict, stat_key: str):
    """Compare all files between prod and dev for one directory."""
    prod_map = _build_slug_map(prod_dir, extensions)
    dev_slugs = {f.name for f in dev_dir.glob('*.md')} if dev_dir.exists() else set()
    all_slugs = sorted(set(prod_map.keys()) | dev_slugs)

    for slug in all_slugs:
        stats[stat_key] += 1
        in_prod = slug in prod_map
        in_dev = slug in dev_slugs

        if in_prod and not in_dev:
            print(f'[PROD ONLY] {slug}')
            stats['prod_only'] += 1
            stats['discrepancies'] += 1
            choice = input('  Copy to dev? (y)es / (n)o: ').strip().lower()
            if choice == 'y':
                dev_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(prod_map[slug], dev_dir / slug)
                stats['kept_prod'] += 1
                print(f'  -> Copied to dev')
            continue

        if in_dev and not in_prod:
            print(f'[DEV ONLY]  {slug}')
            stats['dev_only'] += 1
            stats['discrepancies'] += 1
            choice = input('  Copy to prod? (y)es / (n)o: ').strip().lower()
            if choice == 'y':
                prod_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dev_dir / slug, prod_dir / slug)
                stats['kept_dev'] += 1
                print(f'  -> Copied to prod')
            continue

        # Both exist — compare bodies
        prod_body = _read_body(prod_map[slug])
        dev_body = _read_body(dev_dir / slug)

        if prod_body == dev_body:
            continue

        # Discrepancy found
        stats['discrepancies'] += 1
        diff = _diff_lines(prod_body, dev_body)
        changed = _count_changed_lines(diff)
        is_small = changed <= DIFF_TRUNCATE

        print(f'[DIFF] {slug}  ({changed} changed lines)')
        _show_diff(diff, slug)

        choice = _prompt_choice(is_small)

        if choice == 'p':
            # Keep prod: overwrite dev
            shutil.copy2(prod_map[slug], dev_dir / slug)
            _update_metadata_entry(slug, subdir, prod_body)
            stats['kept_prod'] += 1
            print(f'  -> Kept prod version')

        elif choice == 'd':
            # Keep dev: overwrite prod
            shutil.copy2(dev_dir / slug, prod_map[slug])
            stats['kept_dev'] += 1
            print(f'  -> Kept dev version')

        elif choice == 'e':
            _edit_and_apply(prod_map[slug], dev_dir / slug, prod_body)
            # Re-read and update metadata
            new_body = _read_body(dev_dir / slug)
            _update_metadata_entry(slug, subdir, new_body)
            stats['edited'] += 1
            print(f'  -> Applied edited version to both')


if __name__ == '__main__':
    sync()
