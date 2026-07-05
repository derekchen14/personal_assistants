"""Seed the standing library of 32 draft posts into database/content.

Idempotent: re-running deletes each library post (by deterministic id and by title) and recreates it,
so the committed database always matches library_spec.py + library_prose.py. Post ids are a stable
hash of the slug, so seeding, cleanup, and the commit stay reproducible.

  python utils/evaluation_suite/seed_library.py          # seed / re-seed all 32
  python utils/evaluation_suite/seed_library.py --clean   # remove them (restore an empty library)
"""
import argparse
import hashlib
import sys
from pathlib import Path

_HUGO_ROOT = Path(__file__).resolve().parents[2]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

from backend.utilities.services import PostService, ContentService
from utils.evaluation_suite.library_spec import LIBRARY
from utils.evaluation_suite.library_prose import PROSE


def _post_id(slug:str) -> str:
    return hashlib.sha1(slug.encode()).hexdigest()[:8]


def _clean(post:dict, service:PostService):
    """Remove a library post by id and by title, plus any orphaned draft file."""
    pid = _post_id(post['slug'])
    service.delete_post(pid)
    for entry in service.list_preview().get('items', []):
        if entry.get('title', '').lower() == post['title'].lower():
            service.delete_post(entry['post_id'])
    orphan = service._content_dir / 'drafts' / (service._slugify(post['title']) + '.md')
    orphan.unlink(missing_ok=True)


def _seed_one(post:dict, service:PostService, content:ContentService):
    _clean(post, service)
    pid = _post_id(post['slug'])
    created = service.create_post(post['title'], sections=post['sections'], post_id=pid)
    if not created['_success']:
        raise RuntimeError(f"create {post['slug']} failed: {created['_message']}")
    service.update_post(pid, {'tags': post['tags']})
    if post['stage'] == 'prose':
        prose = PROSE[post['slug']]
        for sec_id, sec_name in zip(created['section_ids'], post['sections']):
            content.revise_content(pid, sec_id, prose[sec_name])
    return pid, post['stage']


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--clean', action='store_true', help='remove the library instead of seeding')
    args = parser.parse_args()

    service, content = PostService(), ContentService()
    if args.clean:
        for post in LIBRARY:
            _clean(post, service)
        print(f'removed {len(LIBRARY)} library posts')
        return

    outlines = proses = 0
    for post in LIBRARY:
        _, stage = _seed_one(post, service, content)
        outlines += stage == 'outline'
        proses += stage == 'prose'
    print(f'seeded {len(LIBRARY)} library posts: {outlines} outline-only, {proses} full-prose')


if __name__ == '__main__':
    main()
