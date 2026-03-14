from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DB_DIR = Path(__file__).resolve().parents[2] / 'database'
_CONTENT_DIR = _DB_DIR / 'content'
_METADATA_FILE = _CONTENT_DIR / 'metadata.json'


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_metadata() -> list[dict]:
    if _METADATA_FILE.exists():
        data = json.loads(_METADATA_FILE.read_text(encoding='utf-8'))
        return data.get('entries', [])
    return []


def _save_metadata(entries: list[dict]):
    _CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    _METADATA_FILE.write_text(
        json.dumps({'entries': entries}, indent=2, default=str),
        encoding='utf-8',
    )


def _read_content(filename: str) -> str:
    """Read .md file, strip YAML frontmatter, return body."""
    filepath = _CONTENT_DIR / filename
    if not filepath.exists():
        return ''
    text = filepath.read_text(encoding='utf-8')
    if text.startswith('---'):
        end = text.find('---', 3)
        if end != -1:
            return text[end + 3:].strip()
    return text


def _write_content(filename: str, frontmatter: dict, body: str):
    """Write .md file with YAML frontmatter."""
    filepath = _CONTENT_DIR / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    lines = ['---']
    for k, v in frontmatter.items():
        if isinstance(v, list):
            lines.append(f'{k}: [{", ".join(str(i) for i in v)}]')
        else:
            lines.append(f'{k}: "{v}"' if isinstance(v, str) and ' ' in v else f'{k}: {v}')
    lines.append('---')
    lines.append('')
    lines.append(body)
    filepath.write_text('\n'.join(lines), encoding='utf-8')


def _compute_preview(body: str, max_len: int = 300) -> str:
    clean = body.replace('<!--more-->', '')
    for para in clean.split('\n\n'):
        stripped = para.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('!['):
            continue
        preview = re.sub(r'<[^>]+>', '', stripped)
        if len(preview) > max_len:
            preview = preview[:max_len].rsplit(' ', 1)[0] + '...'
        return preview
    return ''


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    return re.sub(r'-+', '-', slug).strip('-')[:80]


class ToolService:

    def _success(self, result, **metadata):
        envelope = {'status': 'success', 'result': result}
        if metadata:
            envelope['metadata'] = metadata
        return envelope

    def _error(self, category: str, message: str,
               retryable: bool = False, **metadata):
        envelope = {
            'status': 'error',
            'error_category': category,
            'message': message,
            'retryable': retryable,
        }
        if metadata:
            envelope['metadata'] = metadata
        return envelope


class PostService(ToolService):

    def list_preview(self, limit: int = 100) -> dict:
        entries = _load_metadata()
        previews = []
        for e in entries[:limit]:
            previews.append({
                'post_id': e['post_id'],
                'title': e['title'],
                'status': e.get('status'),
                'category': e.get('category'),
                'metadata': {'tags': e.get('tags', []), 'color': e.get('color')},
                'created_at': e.get('created_at'),
                'updated_at': e.get('updated_at'),
                'preview': e.get('preview', ''),
            })
        return self._success(previews, count=len(previews))

    def search(self, query: str = '', status: str | None = None,
               category: str | None = None, limit: int = 20) -> dict:
        entries = _load_metadata()
        results = []
        q = (query or '').lower()
        for e in entries:
            if q:
                searchable = ' '.join([
                    e.get('title', ''),
                    e.get('category', '') or '',
                    ' '.join(e.get('tags', [])),
                ]).lower()
                if q not in searchable:
                    continue
            if status and e.get('status') != status:
                continue
            if category and category.lower() not in (e.get('category', '') or '').lower():
                continue
            results.append({
                'post_id': e['post_id'],
                'title': e['title'],
                'status': e.get('status'),
                'category': e.get('category'),
                'updated_at': e.get('updated_at'),
            })
            if len(results) >= limit:
                break
        return self._success(results, count=len(results))

    def get(self, post_id: str) -> dict:
        entries = _load_metadata()
        for e in entries:
            if e['post_id'] == post_id:
                content = _read_content(e['filename'])
                # Extract sections from ## headings
                sections = []
                for line in content.split('\n'):
                    if line.startswith('## '):
                        sections.append(line[3:].strip())
                result = {
                    'post_id': e['post_id'],
                    'title': e['title'],
                    'status': e.get('status'),
                    'category': e.get('category'),
                    'metadata': {'tags': e.get('tags', []), 'color': e.get('color')},
                    'created_at': e.get('created_at'),
                    'updated_at': e.get('updated_at'),
                    'content': content,
                    'sections': sections,
                    'word_count': e.get('word_count', 0),
                }
                return self._success(result)
        return self._error('not_found', f'Post not found: {post_id}')

    def create(self, title: str, topic: str | None = None,
               category: str | None = None,
               type: str | None = None) -> dict:
        entries = _load_metadata()
        post_id = str(uuid.uuid4())[:8]
        slug = _slugify(title) + '.md'
        status = type if type in ('draft', 'note') else 'draft'
        directory = 'notes' if status == 'note' else 'drafts'
        filename = f'{directory}/{slug}'
        now = _now()

        (_CONTENT_DIR / directory).mkdir(parents=True, exist_ok=True)
        _write_content(filename, {'title': title}, '')

        entry = {
            'post_id': post_id,
            'title': title,
            'status': status,
            'category': category,
            'tags': [],
            'color': '',
            'created_at': now,
            'updated_at': now,
            'preview': '',
            'word_count': 0,
            'filename': filename,
        }
        entries.append(entry)
        _save_metadata(entries)

        return self._success({
            'post_id': post_id,
            'title': title,
            'topic': topic,
            'category': category,
            'status': status,
            'content': '',
            'sections': [],
            'metadata': {},
            'created_at': now,
            'updated_at': now,
        })

    def update(self, post_id: str, updates: dict) -> dict:
        entries = _load_metadata()
        for e in entries:
            if e['post_id'] == post_id:
                # Update metadata fields
                for k in ('title', 'category', 'tags', 'color'):
                    if k in updates:
                        e[k] = updates[k]
                if 'metadata' in updates:
                    meta = updates['metadata']
                    if 'tags' in meta:
                        e['tags'] = meta['tags']
                    if 'color' in meta:
                        e['color'] = meta['color']

                # Handle content update
                if 'content' in updates:
                    body = updates['content']
                    fm = {'title': e['title']}
                    if e.get('tags'):
                        fm['tags'] = e['tags']
                    if e.get('color'):
                        fm['color'] = e['color']
                    _write_content(e['filename'], fm, body)
                    e['preview'] = _compute_preview(body)
                    e['word_count'] = len(re.sub(r'<[^>]+>', '', body).split())

                # Handle status change (move file between dirs)
                new_status = updates.get('status')
                if new_status and new_status != e.get('status'):
                    old_path = _CONTENT_DIR / e['filename']
                    slug = Path(e['filename']).name
                    if new_status == 'published':
                        new_filename = f'posts/{slug}'
                    elif new_status == 'note':
                        new_filename = f'notes/{slug}'
                    else:
                        new_filename = f'drafts/{slug}'
                    new_path = _CONTENT_DIR / new_filename
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    if old_path.exists():
                        old_path.rename(new_path)
                    e['filename'] = new_filename
                    e['status'] = new_status

                e['updated_at'] = _now()
                _save_metadata(entries)

                # Return full object for compatibility
                content = _read_content(e['filename'])
                result = {
                    'post_id': e['post_id'],
                    'title': e['title'],
                    'status': e.get('status'),
                    'category': e.get('category'),
                    'metadata': {'tags': e.get('tags', []), 'color': e.get('color')},
                    'created_at': e.get('created_at'),
                    'updated_at': e.get('updated_at'),
                    'content': content,
                }
                # Merge any extra keys from updates
                for k, v in updates.items():
                    if k not in result and k != 'post_id':
                        result[k] = v
                return self._success(result)
        return self._error('not_found', f'Post not found: {post_id}')

    def delete(self, post_id: str) -> dict:
        entries = _load_metadata()
        for i, e in enumerate(entries):
            if e['post_id'] == post_id:
                removed = entries.pop(i)
                _save_metadata(entries)
                # Delete the .md file
                filepath = _CONTENT_DIR / removed['filename']
                if filepath.exists():
                    filepath.unlink()
                return self._success(
                    {'post_id': post_id, 'title': removed.get('title', '')},
                    action='deleted',
                )
        return self._error('not_found', f'Post not found: {post_id}')


class ContentService(ToolService):

    def generate(self, content_type: str, topic: str | None = None,
                 source_text: str | None = None,
                 instructions: str | None = None) -> dict:
        return self._success({
            'content_type': content_type,
            'topic': topic,
            'instructions': instructions,
            'generated': True,
            'note': 'Content generation delegated to LLM via skill prompt',
        })

    def format(self, content: str, platform: str,
               format_type: str = 'blog') -> dict:
        return self._success({
            'formatted_content': content,
            'platform': platform,
            'format_type': format_type,
        })


class PlatformService(ToolService):

    def __init__(self):
        self._publishers: dict[str, PlatformPublisher] = {
            'substack': SubstackPublisher(),
            'twitter': TwitterPublisher(),
            'linkedin': LinkedInPublisher(),
            'mt1t': MT1TPublisher(),
        }

    def list_platforms(self) -> dict:
        result = []
        for pid, pub in self._publishers.items():
            result.append({
                'id': pid,
                'name': pub.display_name,
                'connected': pub.is_connected(),
                'type': pub.platform_type,
                'max_length': pub.max_length,
            })
        return self._success(result)

    def publish(self, post_id: str, platform: str,
                action: str = 'publish', scheduled_at: str | None = None) -> dict:
        pub = self._publishers.get(platform)
        if not pub:
            available = ', '.join(self._publishers.keys())
            return self._error(
                'invalid_input',
                f'Unknown platform: {platform}. Available: {available}',
            )
        if not pub.is_connected():
            return self._error(
                'auth_error',
                f'{pub.display_name} is not connected. '
                f'Set {pub.required_env_vars()} in .keys or .env.',
            )

        post_svc = PostService()
        post_result = post_svc.get(post_id)
        if post_result['status'] != 'success':
            return post_result
        post = post_result['result']

        if action == 'publish':
            return pub.publish(post)
        elif action == 'schedule':
            return pub.schedule(post, scheduled_at or '')
        elif action == 'unpublish':
            return pub.unpublish(post)
        return self._error('invalid_input', f'Unknown action: {action}')

    def get_status(self, post_id: str, platform: str) -> dict:
        pub = self._publishers.get(platform)
        if not pub:
            available = ', '.join(self._publishers.keys())
            return self._error(
                'invalid_input',
                f'Unknown platform: {platform}. Available: {available}',
            )
        if not pub.is_connected():
            return self._error(
                'auth_error',
                f'{pub.display_name} is not connected. '
                f'Set {pub.required_env_vars()} in .keys or .env.',
            )
        return pub.get_status(post_id)

    def format_for_platform(self, content: str, platform: str) -> dict:
        pub = self._publishers.get(platform)
        if not pub:
            return self._error('invalid_input', f'Unknown platform: {platform}')
        return pub.format_content(content)


class PlatformPublisher(ToolService):

    display_name: str = ''
    platform_type: str = ''
    max_length: int | None = None

    def is_connected(self) -> bool:
        return False

    def required_env_vars(self) -> list[str]:
        return []

    def publish(self, post: dict) -> dict:
        return self._error('server_error', 'Not implemented')

    def schedule(self, post: dict, scheduled_at: str) -> dict:
        return self._error('platform_error', 'Scheduling not supported on this platform')

    def unpublish(self, post: dict) -> dict:
        return self._error('platform_error', 'Unpublish not supported on this platform')

    def get_status(self, post_id: str) -> dict:
        return self._error('platform_error', 'Status check not supported on this platform')

    def format_content(self, content: str) -> dict:
        return self._success({'formatted': content})


# ── Substack (smart stub) ────────────────────────────────────────────

class SubstackPublisher(PlatformPublisher):

    display_name = 'Substack'
    platform_type = 'newsletter'
    max_length = None

    def is_connected(self) -> bool:
        return True

    def required_env_vars(self) -> list[str]:
        return []

    def publish(self, post: dict) -> dict:
        html = self._markdown_to_html(post.get('content', ''))
        title = post.get('title', 'Untitled')
        full_html = f'<h1>{title}</h1>\n{html}'

        tmp = Path(tempfile.gettempdir()) / f'substack_{post["post_id"]}.html'
        tmp.write_text(full_html, encoding='utf-8')

        return {
            'status': 'manual_required',
            'message': (
                'Substack has no public API. Content has been formatted as '
                'Substack-ready HTML. Copy-paste from the file below into '
                'the Substack editor.'
            ),
            'result': {
                'post_id': post['post_id'],
                'platform': 'substack',
                'title': title,
                'file_path': str(tmp),
                'content_length': len(full_html),
                'action': 'publish',
            },
        }

    def schedule(self, post: dict, scheduled_at: str) -> dict:
        result = self.publish(post)
        if result.get('result'):
            result['result']['scheduled_at'] = scheduled_at
            result['result']['action'] = 'schedule'
            result['message'] += f' Target publish date: {scheduled_at}'
        return result

    def get_status(self, post_id: str) -> dict:
        return self._error(
            'platform_error',
            'Substack has no public API — cannot check publication status.',
        )

    def format_content(self, content: str) -> dict:
        html = self._markdown_to_html(content)
        return self._success({
            'formatted': html,
            'format': 'html',
            'platform': 'substack',
        })

    def _markdown_to_html(self, md: str) -> str:
        lines = md.split('\n')
        html_lines = []
        in_code_block = False
        in_list = False

        for line in lines:
            if line.startswith('```'):
                if in_code_block:
                    html_lines.append('</code></pre>')
                    in_code_block = False
                else:
                    lang = line[3:].strip()
                    cls = f' class="language-{lang}"' if lang else ''
                    html_lines.append(f'<pre><code{cls}>')
                    in_code_block = True
                continue

            if in_code_block:
                html_lines.append(line)
                continue

            if line.startswith('# '):
                html_lines.append(f'<h2>{line[2:]}</h2>')
            elif line.startswith('## '):
                html_lines.append(f'<h3>{line[3:]}</h3>')
            elif line.startswith('### '):
                html_lines.append(f'<h4>{line[4:]}</h4>')
            elif line.startswith('- ') or line.startswith('* '):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                html_lines.append(f'<li>{line[2:]}</li>')
            else:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                if line.strip():
                    formatted = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
                    formatted = re.sub(r'\*(.+?)\*', r'<em>\1</em>', formatted)
                    formatted = re.sub(r'`(.+?)`', r'<code>\1</code>', formatted)
                    html_lines.append(f'<p>{formatted}</p>')

        if in_list:
            html_lines.append('</ul>')
        if in_code_block:
            html_lines.append('</code></pre>')
        return '\n'.join(html_lines)


# ── Twitter/X ─────────────────────────────────────────────────────────

class TwitterPublisher(PlatformPublisher):

    display_name = 'Twitter/X'
    platform_type = 'social'
    max_length = 280

    def is_connected(self) -> bool:
        return bool(
            os.getenv('TWITTER_API_KEY')
            and os.getenv('TWITTER_API_SECRET')
            and os.getenv('TWITTER_ACCESS_TOKEN')
            and os.getenv('TWITTER_ACCESS_SECRET')
        )

    def required_env_vars(self) -> list[str]:
        return [
            'TWITTER_API_KEY', 'TWITTER_API_SECRET',
            'TWITTER_ACCESS_TOKEN', 'TWITTER_ACCESS_SECRET',
        ]

    def publish(self, post: dict) -> dict:
        try:
            import tweepy
        except ImportError:
            return self._error(
                'server_error',
                'tweepy is not installed. Run: pip install tweepy',
            )

        client = tweepy.Client(
            consumer_key=os.getenv('TWITTER_API_KEY'),
            consumer_secret=os.getenv('TWITTER_API_SECRET'),
            access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
            access_token_secret=os.getenv('TWITTER_ACCESS_SECRET'),
        )

        content = post.get('content', '') or post.get('title', '')
        tweets = self._split_into_tweets(content)
        posted_ids = []

        try:
            reply_to = None
            for i, text in enumerate(tweets):
                resp = client.create_tweet(
                    text=text,
                    in_reply_to_tweet_id=reply_to,
                )
                tweet_id = resp.data['id']
                posted_ids.append(tweet_id)
                reply_to = tweet_id

            return self._success({
                'post_id': post['post_id'],
                'platform': 'twitter',
                'tweet_ids': posted_ids,
                'tweet_count': len(posted_ids),
                'thread': len(posted_ids) > 1,
                'action': 'publish',
            })
        except tweepy.TweepyException as e:
            return self._error(
                'platform_error', f'Twitter API error: {e}',
                retryable='rate' in str(e).lower(),
            )

    def schedule(self, post: dict, scheduled_at: str) -> dict:
        return self._error(
            'platform_error',
            'Twitter free/basic API does not support native scheduling.',
        )

    def get_status(self, post_id: str) -> dict:
        try:
            import tweepy
        except ImportError:
            return self._error('server_error', 'tweepy is not installed.')

        client = tweepy.Client(
            consumer_key=os.getenv('TWITTER_API_KEY'),
            consumer_secret=os.getenv('TWITTER_API_SECRET'),
            access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
            access_token_secret=os.getenv('TWITTER_ACCESS_SECRET'),
        )

        try:
            resp = client.get_tweet(
                post_id, tweet_fields=['created_at', 'public_metrics'],
            )
            if resp.data:
                return self._success({
                    'platform': 'twitter',
                    'tweet_id': post_id,
                    'text': resp.data.text,
                    'created_at': str(resp.data.created_at),
                    'metrics': resp.data.public_metrics,
                    'live': True,
                    'url': f'https://x.com/i/status/{post_id}',
                })
            return self._error('not_found', f'Tweet not found: {post_id}')
        except tweepy.TweepyException as e:
            return self._error(
                'platform_error', f'Twitter API error: {e}',
                retryable='rate' in str(e).lower(),
            )

    def format_content(self, content: str) -> dict:
        tweets = self._split_into_tweets(content)
        return self._success({
            'formatted': tweets,
            'format': 'thread',
            'platform': 'twitter',
            'tweet_count': len(tweets),
        })

    def _split_into_tweets(self, content: str) -> list[str]:
        words = content.split()
        tweets = []
        current = ''
        for word in words:
            candidate = f'{current} {word}'.strip() if current else word
            if len(candidate) > self.max_length:
                if current:
                    tweets.append(current)
                current = word
            else:
                current = candidate
        if current:
            tweets.append(current)
        return tweets or [content[:self.max_length]]

    def _estimate_thread_count(self, post: dict) -> int:
        content = post.get('content', '') or post.get('title', '')
        return max(1, len(content) // self.max_length + 1)


# ── LinkedIn ──────────────────────────────────────────────────────────

class LinkedInPublisher(PlatformPublisher):

    display_name = 'LinkedIn'
    platform_type = 'social'
    max_length = 3000
    _API_BASE = 'https://api.linkedin.com/v2'

    def is_connected(self) -> bool:
        return bool(os.getenv('LINKEDIN_ACCESS_TOKEN'))

    def required_env_vars(self) -> list[str]:
        return ['LINKEDIN_ACCESS_TOKEN', 'LINKEDIN_PERSON_URN']

    def _client(self):
        import httpx
        return httpx.Client(
            base_url=self._API_BASE,
            headers={
                'Authorization': f'Bearer {os.getenv("LINKEDIN_ACCESS_TOKEN")}',
                'Content-Type': 'application/json',
                'X-Restli-Protocol-Version': '2.0.0',
            },
            timeout=15.0,
        )

    def publish(self, post: dict) -> dict:
        try:
            import httpx
        except ImportError:
            return self._error('server_error', 'httpx is not installed. Run: pip install httpx')

        person_urn = os.getenv('LINKEDIN_PERSON_URN', '')
        content = post.get('content', '') or post.get('title', '')
        formatted = self._format_for_linkedin(content, post.get('metadata', {}))

        body = {
            'author': person_urn,
            'commentary': formatted,
            'visibility': 'PUBLIC',
            'distribution': {
                'feedDistribution': 'MAIN_FEED',
                'targetEntities': [],
                'thirdPartyDistributionChannels': [],
            },
            'lifecycleState': 'PUBLISHED',
        }

        try:
            with self._client() as client:
                resp = client.post('/posts', json=body)
                if resp.status_code == 201:
                    post_urn = resp.headers.get('x-restli-id', '')
                    return self._success({
                        'post_id': post['post_id'],
                        'platform': 'linkedin',
                        'post_urn': post_urn,
                        'content_length': len(formatted),
                        'action': 'publish',
                    })
                elif resp.status_code == 401:
                    return self._error(
                        'auth_error',
                        'LinkedIn access token expired or invalid. Refresh the token.',
                        retryable=True,
                    )
                elif resp.status_code == 429:
                    return self._error(
                        'rate_limit',
                        'LinkedIn rate limit exceeded. Try again later.',
                        retryable=True,
                    )
                else:
                    return self._error(
                        'platform_error',
                        f'LinkedIn API error {resp.status_code}: {resp.text}',
                        retryable=resp.status_code >= 500,
                    )
        except httpx.HTTPError as e:
            return self._error(
                'server_error', f'LinkedIn request failed: {e}', retryable=True,
            )

    def schedule(self, post: dict, scheduled_at: str) -> dict:
        return self._error(
            'platform_error',
            'LinkedIn API does not support native scheduling. '
            'Use the schedule flow to set a reminder instead.',
        )

    def get_status(self, post_id: str) -> dict:
        try:
            import httpx
        except ImportError:
            return self._error('server_error', 'httpx is not installed.')

        try:
            with self._client() as client:
                resp = client.get(f'/posts/{post_id}')
                if resp.status_code == 200:
                    data = resp.json()
                    return self._success({
                        'platform': 'linkedin',
                        'post_urn': post_id,
                        'lifecycle_state': data.get('lifecycleState', 'unknown'),
                        'live': data.get('lifecycleState') == 'PUBLISHED',
                        'created_at': data.get('createdAt'),
                    })
                elif resp.status_code == 404:
                    return self._error('not_found', f'LinkedIn post not found: {post_id}')
                else:
                    return self._error(
                        'platform_error',
                        f'LinkedIn API error {resp.status_code}: {resp.text}',
                        retryable=resp.status_code >= 500,
                    )
        except httpx.HTTPError as e:
            return self._error('server_error', f'LinkedIn request failed: {e}', retryable=True)

    def format_content(self, content: str) -> dict:
        formatted = self._format_for_linkedin(content, {})
        return self._success({
            'formatted': formatted,
            'format': 'text',
            'platform': 'linkedin',
            'truncated': len(content) > self.max_length,
        })

    def _format_for_linkedin(self, content: str, metadata: dict) -> str:
        text = re.sub(r'#{1,6}\s+', '', content)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'\1 (\2)', text)

        tags = metadata.get('tags', [])
        if tags:
            hashtags = ' '.join(f'#{t.replace(" ", "")}' for t in tags)
            text = f'{text}\n\n{hashtags}'

        if len(text) > self.max_length:
            text = text[:self.max_length - 3] + '...'
        return text


# ── MT1T (Jekyll + GitHub Pages) ──────────────────────────────────────

class MT1TPublisher(PlatformPublisher):

    display_name = 'More Than One Turn'
    platform_type = 'blog'
    max_length = None

    def is_connected(self) -> bool:
        repo = os.getenv('MT1T_REPO_PATH', '')
        return bool(repo) and Path(repo).is_dir()

    def required_env_vars(self) -> list[str]:
        return ['MT1T_REPO_PATH']

    def _repo_path(self) -> Path:
        return Path(os.getenv('MT1T_REPO_PATH', ''))

    def _posts_dir(self) -> Path:
        return self._repo_path() / '_posts'

    def _drafts_dir(self) -> Path:
        return self._repo_path() / '_drafts'

    def _build_filename(self, post: dict) -> str:
        date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        slug = _slugify(post.get('title', 'untitled'))
        return f'{date}-{slug}.md'

    def _build_frontmatter(self, post: dict) -> str:
        title = post.get('title', 'Untitled')
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        meta = post.get('metadata', {})
        tags = meta.get('tags', [])
        color = meta.get('color', 'rgb(214, 93, 14)')

        tag_str = ', '.join(tags) if tags else ''
        return (
            '---\n'
            'layout: post\n'
            f'title: "{title}"\n'
            f"date: '{now}'\n"
            f'tags: [{tag_str}]\n'
            f'color: {color}\n'
            'excerpt_separator: <!--more-->\n'
            '---\n'
        )

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ['git', *args],
            cwd=self._repo_path(),
            capture_output=True, text=True, timeout=30,
        )

    def publish(self, post: dict) -> dict:
        posts_dir = self._posts_dir()
        if not posts_dir.exists():
            return self._error(
                'server_error',
                f'_posts directory not found at {posts_dir}',
            )

        filename = self._build_filename(post)
        filepath = posts_dir / filename
        content = self._build_frontmatter(post) + '\n' + post.get('content', '')
        filepath.write_text(content, encoding='utf-8')

        result = self._git('add', str(filepath))
        if result.returncode != 0:
            return self._error('server_error', f'git add failed: {result.stderr}')

        title = post.get('title', 'Untitled')
        result = self._git('commit', '-m', f'Publish: {title}')
        if result.returncode != 0:
            return self._error('server_error', f'git commit failed: {result.stderr}')

        result = self._git('push')
        if result.returncode != 0:
            return self._error(
                'server_error', f'git push failed: {result.stderr}', retryable=True,
            )

        return self._success({
            'post_id': post['post_id'],
            'platform': 'mt1t',
            'filename': filename,
            'file_path': str(filepath),
            'action': 'publish',
        })

    def schedule(self, post: dict, scheduled_at: str) -> dict:
        drafts_dir = self._drafts_dir()
        drafts_dir.mkdir(parents=True, exist_ok=True)

        filename = self._build_filename(post)
        filepath = drafts_dir / filename

        meta = dict(post.get('metadata', {}))
        meta['publish_date'] = scheduled_at
        post_copy = {**post, 'metadata': meta}

        content = self._build_frontmatter(post_copy) + '\n' + post.get('content', '')
        filepath.write_text(content, encoding='utf-8')

        return self._success({
            'post_id': post['post_id'],
            'platform': 'mt1t',
            'filename': filename,
            'file_path': str(filepath),
            'scheduled_at': scheduled_at,
            'action': 'schedule',
            'note': 'Written to _drafts/. Move to _posts/ on publish date.',
        })

    def unpublish(self, post: dict) -> dict:
        posts_dir = self._posts_dir()
        slug = _slugify(post.get('title', ''))
        matches = list(posts_dir.glob(f'*-{slug}.md'))

        if not matches:
            return self._error(
                'not_found',
                f'No published post matching "{post.get("title", "")}" found in _posts/',
            )

        filepath = matches[0]
        result = self._git('rm', str(filepath))
        if result.returncode != 0:
            return self._error('server_error', f'git rm failed: {result.stderr}')

        title = post.get('title', 'Untitled')
        result = self._git('commit', '-m', f'Unpublish: {title}')
        if result.returncode != 0:
            return self._error('server_error', f'git commit failed: {result.stderr}')

        result = self._git('push')
        if result.returncode != 0:
            return self._error(
                'server_error', f'git push failed: {result.stderr}', retryable=True,
            )

        return self._success({
            'post_id': post['post_id'],
            'platform': 'mt1t',
            'filename': filepath.name,
            'action': 'unpublish',
        })

    def get_status(self, post_id: str) -> dict:
        post_svc = PostService()
        post_result = post_svc.get(post_id)
        if post_result['status'] != 'success':
            return post_result
        post = post_result['result']

        slug = _slugify(post.get('title', ''))
        posts_dir = self._posts_dir()
        matches = list(posts_dir.glob(f'*-{slug}.md'))

        if matches:
            filepath = matches[0]
            return self._success({
                'platform': 'mt1t',
                'post_id': post_id,
                'filename': filepath.name,
                'file_path': str(filepath),
                'live': True,
            })

        drafts_dir = self._drafts_dir()
        draft_matches = list(drafts_dir.glob(f'*-{slug}.md'))
        if draft_matches:
            return self._success({
                'platform': 'mt1t',
                'post_id': post_id,
                'filename': draft_matches[0].name,
                'file_path': str(draft_matches[0]),
                'live': False,
                'status': 'draft',
            })

        return self._success({
            'platform': 'mt1t',
            'post_id': post_id,
            'live': False,
            'status': 'not_published',
        })

    def format_content(self, content: str) -> dict:
        return self._success({
            'formatted': content,
            'format': 'markdown',
            'platform': 'mt1t',
        })
