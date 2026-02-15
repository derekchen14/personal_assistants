from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DB_DIR = Path(__file__).resolve().parents[2] / 'database'
_POSTS_FILE = _DB_DIR / 'posts.json'


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_posts() -> list[dict]:
    if _POSTS_FILE.exists():
        return json.loads(_POSTS_FILE.read_text(encoding='utf-8'))
    return []


def _save_posts(posts: list[dict]):
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    _POSTS_FILE.write_text(
        json.dumps(posts, indent=2, default=str), encoding='utf-8',
    )


class PostService:

    def search(self, query: str = '', status: str | None = None,
               category: str | None = None, limit: int = 20) -> dict:
        posts = _load_posts()
        results = []
        for p in posts:
            if query and query.lower() not in json.dumps(p).lower():
                continue
            if status and p.get('status') != status:
                continue
            if category and category.lower() not in (p.get('category', '') or '').lower():
                continue
            results.append({
                'post_id': p['post_id'],
                'title': p['title'],
                'status': p['status'],
                'category': p.get('category'),
                'updated_at': p.get('updated_at'),
            })
            if len(results) >= limit:
                break
        return {'status': 'success', 'result': results, 'count': len(results)}

    def get(self, post_id: str) -> dict:
        posts = _load_posts()
        for p in posts:
            if p['post_id'] == post_id:
                return {'status': 'success', 'result': p}
        return {'status': 'error', 'message': f'Post not found: {post_id}'}

    def create(self, title: str, topic: str | None = None,
               category: str | None = None) -> dict:
        posts = _load_posts()
        post = {
            'post_id': str(uuid.uuid4())[:8],
            'title': title,
            'topic': topic,
            'category': category,
            'status': 'draft',
            'content': '',
            'outline': [],
            'sections': [],
            'metadata': {},
            'created_at': _now(),
            'updated_at': _now(),
        }
        posts.append(post)
        _save_posts(posts)
        return {'status': 'success', 'result': post}

    def update(self, post_id: str, updates: dict) -> dict:
        posts = _load_posts()
        for p in posts:
            if p['post_id'] == post_id:
                for k, v in updates.items():
                    if k != 'post_id':
                        p[k] = v
                p['updated_at'] = _now()
                _save_posts(posts)
                return {'status': 'success', 'result': p}
        return {'status': 'error', 'message': f'Post not found: {post_id}'}


class ContentService:

    def generate(self, content_type: str, topic: str | None = None,
                 source_text: str | None = None,
                 instructions: str | None = None) -> dict:
        return {
            'status': 'success',
            'result': {
                'content_type': content_type,
                'topic': topic,
                'instructions': instructions,
                'generated': True,
                'note': 'Content generation delegated to LLM via skill prompt',
            },
        }

    def format(self, content: str, platform: str,
               format_type: str = 'blog') -> dict:
        return {
            'status': 'success',
            'result': {
                'formatted_content': content,
                'platform': platform,
                'format_type': format_type,
            },
        }


class PlatformService:

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
        return {'status': 'success', 'result': result}

    def publish(self, post_id: str, platform: str,
                action: str = 'publish', scheduled_at: str | None = None) -> dict:
        pub = self._publishers.get(platform)
        if not pub:
            available = ', '.join(self._publishers.keys())
            return {
                'status': 'error',
                'message': f'Unknown platform: {platform}. Available: {available}',
            }
        if not pub.is_connected():
            return {
                'status': 'error',
                'message': f'{pub.display_name} is not connected. '
                           f'Set {pub.required_env_vars()} in .keys or .env.',
            }

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
        return {'status': 'error', 'message': f'Unknown action: {action}'}

    def format_for_platform(self, content: str, platform: str) -> dict:
        pub = self._publishers.get(platform)
        if not pub:
            return {'status': 'error', 'message': f'Unknown platform: {platform}'}
        return pub.format_content(content)


class PlatformPublisher:

    display_name: str = ''
    platform_type: str = ''
    max_length: int | None = None

    def is_connected(self) -> bool:
        return False

    def required_env_vars(self) -> list[str]:
        return []

    def publish(self, post: dict) -> dict:
        return {'status': 'error', 'message': 'Not implemented'}

    def schedule(self, post: dict, scheduled_at: str) -> dict:
        return {'status': 'error', 'message': 'Scheduling not supported on this platform'}

    def unpublish(self, post: dict) -> dict:
        return {'status': 'error', 'message': 'Unpublish not supported on this platform'}

    def format_content(self, content: str) -> dict:
        return {'status': 'success', 'result': {'formatted': content}}


class SubstackPublisher(PlatformPublisher):

    display_name = 'Substack'
    platform_type = 'newsletter'
    max_length = None

    def is_connected(self) -> bool:
        return bool(os.getenv('SUBSTACK_API_KEY'))

    def required_env_vars(self) -> list[str]:
        return ['SUBSTACK_API_KEY', 'SUBSTACK_PUBLICATION_ID']

    def publish(self, post: dict) -> dict:
        # TODO: Implement Substack API integration
        # POST https://substack.com/api/v1/drafts
        # Headers: Authorization: Bearer {SUBSTACK_API_KEY}
        # Body: { title, body_html, publication_id, type: "newsletter" }
        return {
            'status': 'stub',
            'message': 'Substack publishing not yet wired. Post ready for manual upload.',
            'result': {
                'post_id': post['post_id'],
                'platform': 'substack',
                'title': post.get('title', ''),
                'content_length': len(post.get('content', '')),
                'action': 'publish',
            },
        }

    def schedule(self, post: dict, scheduled_at: str) -> dict:
        # TODO: Substack supports scheduling via draft_created_at
        return {
            'status': 'stub',
            'message': f'Substack scheduling not yet wired. Target: {scheduled_at}',
            'result': {
                'post_id': post['post_id'],
                'platform': 'substack',
                'scheduled_at': scheduled_at,
                'action': 'schedule',
            },
        }

    def format_content(self, content: str) -> dict:
        # Substack accepts HTML. Convert markdown to HTML here.
        return {
            'status': 'success',
            'result': {
                'formatted': content,
                'format': 'html',
                'platform': 'substack',
                'note': 'Substack accepts HTML body content',
            },
        }


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
        # TODO: Implement Twitter API v2 integration
        # POST https://api.twitter.com/2/tweets
        # OAuth 1.0a signing with consumer + access tokens
        # Body: { text: "..." }
        # For threads: chain tweets with reply_to_tweet_id
        return {
            'status': 'stub',
            'message': 'Twitter publishing not yet wired. Post ready for manual posting.',
            'result': {
                'post_id': post['post_id'],
                'platform': 'twitter',
                'title': post.get('title', ''),
                'thread_count': self._estimate_thread_count(post),
                'action': 'publish',
            },
        }

    def schedule(self, post: dict, scheduled_at: str) -> dict:
        # TODO: Twitter supports scheduled tweets via scheduled_at parameter
        return {
            'status': 'stub',
            'message': f'Twitter scheduling not yet wired. Target: {scheduled_at}',
            'result': {
                'post_id': post['post_id'],
                'platform': 'twitter',
                'scheduled_at': scheduled_at,
                'action': 'schedule',
            },
        }

    def format_content(self, content: str) -> dict:
        tweets = self._split_into_tweets(content)
        return {
            'status': 'success',
            'result': {
                'formatted': tweets,
                'format': 'thread',
                'platform': 'twitter',
                'tweet_count': len(tweets),
                'note': f'Split into {len(tweets)}-tweet thread',
            },
        }

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


class LinkedInPublisher(PlatformPublisher):

    display_name = 'LinkedIn'
    platform_type = 'social'
    max_length = 3000

    def is_connected(self) -> bool:
        return bool(os.getenv('LINKEDIN_ACCESS_TOKEN'))

    def required_env_vars(self) -> list[str]:
        return ['LINKEDIN_ACCESS_TOKEN', 'LINKEDIN_PERSON_URN']

    def publish(self, post: dict) -> dict:
        # TODO: Implement LinkedIn API integration
        # POST https://api.linkedin.com/v2/posts
        # Headers: Authorization: Bearer {LINKEDIN_ACCESS_TOKEN}
        # Body: { author, commentary, visibility, distribution, lifecycleState }
        return {
            'status': 'stub',
            'message': 'LinkedIn publishing not yet wired. Post ready for manual posting.',
            'result': {
                'post_id': post['post_id'],
                'platform': 'linkedin',
                'title': post.get('title', ''),
                'content_length': len(post.get('content', '')),
                'action': 'publish',
            },
        }

    def format_content(self, content: str) -> dict:
        truncated = content[:self.max_length] if len(content) > self.max_length else content
        return {
            'status': 'success',
            'result': {
                'formatted': truncated,
                'format': 'text',
                'platform': 'linkedin',
                'truncated': len(content) > self.max_length,
                'note': 'LinkedIn posts support plain text with basic formatting',
            },
        }


class MT1TPublisher(PlatformPublisher):

    display_name = 'More Than One Turn'
    platform_type = 'blog'
    max_length = None

    def is_connected(self) -> bool:
        return bool(os.getenv('MT1T_API_KEY'))

    def required_env_vars(self) -> list[str]:
        return ['MT1T_API_KEY', 'MT1T_BASE_URL']

    def publish(self, post: dict) -> dict:
        # TODO: Implement MT1T blog API integration
        # The endpoint and auth method depend on the blog's CMS
        # (Ghost, WordPress, custom, etc.)
        # POST {MT1T_BASE_URL}/api/posts
        # Headers: Authorization: Bearer {MT1T_API_KEY}
        # Body: { title, html, status: "published", tags, ... }
        return {
            'status': 'stub',
            'message': 'MT1T publishing not yet wired. Post ready for manual upload.',
            'result': {
                'post_id': post['post_id'],
                'platform': 'mt1t',
                'title': post.get('title', ''),
                'content_length': len(post.get('content', '')),
                'action': 'publish',
            },
        }

    def schedule(self, post: dict, scheduled_at: str) -> dict:
        # TODO: Most blog CMS platforms support scheduling via published_at
        return {
            'status': 'stub',
            'message': f'MT1T scheduling not yet wired. Target: {scheduled_at}',
            'result': {
                'post_id': post['post_id'],
                'platform': 'mt1t',
                'scheduled_at': scheduled_at,
                'action': 'schedule',
            },
        }

    def format_content(self, content: str) -> dict:
        return {
            'status': 'success',
            'result': {
                'formatted': content,
                'format': 'markdown',
                'platform': 'mt1t',
                'note': 'MT1T accepts markdown or HTML',
            },
        }
