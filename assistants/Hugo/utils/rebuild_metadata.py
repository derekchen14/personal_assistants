"""Rebuild metadata.json from disk content.

Recomputes preview, word_count, and section_ids for every entry. With --apply, the index is synced
to disk: new files are added and entries for missing files are removed.

Usage:
    python utils/rebuild_metadata.py # dry-run (shows changes) python utils/rebuild_metadata.py
    --apply # sync index to disk
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.utilities.services import PostService


def rebuild(apply=False):
    svc = PostService()

    # First, sync any new files on disk
    sync = svc.sync_check()
    if sync['added']:
        for item in sync['added']:
            print(f'  Added: {item["filename"]}')
    if sync['missing']:
        for item in sync['missing']:
            fname = item["filename"]
            if apply:
                print(f'  Removed from index: {fname}')
            else:
                print(f'  Missing from index: {fname}, would be removed')

    entries = svc._load_metadata()
    changes = 0

    if sync['missing']:
        missing_names = {item['filename'] for item in sync['missing']}
        entries = [ent for ent in entries if ent['filename'] not in missing_names]
        changes += len(missing_names)

    for ent in entries:
        content = svc._read_content(ent['filename'])
        if not content:
            continue

        sections = svc._extract_sections(content)
        section_ids = [sec['sec_id'] for sec in sections]

        import re
        word_count = len(re.sub(r'<[^>]+>', '', content).split())
        preview = svc._compute_preview(content)

        updated = False
        if ent.get('preview', '') != preview:
            print(f'  Preview updated: {ent["filename"]}')
            ent['preview'] = preview
            updated = True
        if ent.get('word_count') != word_count:
            ent['word_count'] = word_count
            updated = True
        if updated:
            changes += 1

    print(f'\n{changes} entries updated out of {len(entries)} total.')

    if apply:
        svc._save_metadata(entries)
        print('metadata.json written.')
    else:
        print('Dry run — pass --apply to write changes.')


if __name__ == '__main__':
    rebuild(apply='--apply' in sys.argv)
