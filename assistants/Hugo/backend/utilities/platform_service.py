from __future__ import annotations

import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from backend.utilities.services import ToolService


class PlatformService(ToolService):

    def __init__(self):
        super().__init__()
        self._publishers: dict[str, PlatformPublisher] = {
            'substack': SubstackPublisher(),
            'twitter': TwitterPublisher(),
            'linkedin': LinkedInPublisher(),
            'mt1t': MT1TPublisher(),
        }

    def release_post(self, post_id:str, platform:str,
                     scheduled_at:str|None=None) -> dict:
        pub = self._publishers.get(platform)
        if not pub:
            available = ', '.join(self._publishers.keys())
            return self._error('invalid_input',
                f'Unknown platform: {platform}. Available: {available}')
        if not pub.is_connected():
            return self._error('auth_error',
                f'{pub.display_name} is not connected. Set {pub.required_env_vars()} in .keys or .env.')

        from backend.utilities.post_service import PostService
        post_svc = PostService()
        post_result = post_svc.read_metadata(post_id, include_outline=True)
        if not post_result.get('_success'):
            return post_result

        entries = self._load_metadata()
        ent = self._find_entry(entries, post_id)
        content = self._read_content(ent['filename']) if ent else ''
        post = {
            'post_id': post_id,
            'title': post_result.get('title', ''),
            'content': content,
            'metadata': {'tags': post_result.get('tags', []), 'color': post_result.get('color', '')},
        }

        if scheduled_at:
            return pub.schedule(post, scheduled_at)
        return pub.publish(post)

    def promote_post(self, post_id:str, platform:str, action:str='promote') -> dict:
        pub = self._publishers.get(platform)
        if not pub:
            available = ', '.join(self._publishers.keys())
            return self._error('invalid_input',
                f'Unknown platform: {platform}. Available: {available}')
        if not pub.is_connected():
            return self._error('auth_error',
                f'{pub.display_name} is not connected.')

        if hasattr(pub, 'promote'):
            return pub.promote(post_id, action)
        return self._error('platform_error',
            f'{pub.display_name} does not support promotion actions.')

    def cancel_release(self, post_id:str, platform:str) -> dict:
        pub = self._publishers.get(platform)
        if not pub:
            available = ', '.join(self._publishers.keys())
            return self._error('invalid_input',
                f'Unknown platform: {platform}. Available: {available}')
        if not pub.is_connected():
            return self._error('auth_error',
                f'{pub.display_name} is not connected.')

        entries = self._load_metadata()
        ent = self._find_entry(entries, post_id)
        if not ent:
            return self._error('not_found', f'Post not found: {post_id}')

        content = self._read_content(ent['filename'])
        post = {
            'post_id': post_id,
            'title': ent.get('title', ''),
            'content': content,
            'metadata': {'tags': ent.get('tags', [])},
        }
        return pub.unpublish(post)

    def list_channels(self) -> dict:
        result = []
        for pid, pub in self._publishers.items():
            result.append({
                'id': pid,
                'name': pub.display_name,
                'connected': pub.is_connected(),
                'type': pub.platform_type,
                'max_length': pub.max_length,
            })
        return self._success(channels=result)

    def channel_status(self, post_id:str, platform:str) -> dict:
        pub = self._publishers.get(platform)
        if not pub:
            available = ', '.join(self._publishers.keys())
            return self._error('invalid_input',
                f'Unknown platform: {platform}. Available: {available}')
        if not pub.is_connected():
            return self._error('auth_error',
                f'{pub.display_name} is not connected. Set {pub.required_env_vars()} in .keys or .env.')
        return pub.get_status(post_id)


# ── Publishers ────────────────────────────────────────────────────────

class PlatformPublisher(ToolService):

    display_name: str = ''
    platform_type: str = ''
    max_length: int | None = None

    def is_connected(self) -> bool:
        return False

    def required_env_vars(self) -> list[str]:
        return []

    def publish(self, post:dict) -> dict:
        return self._error('server_error', 'Not implemented')

    def schedule(self, post:dict, scheduled_at:str) -> dict:
        return self._error('platform_error', 'Scheduling not supported on this platform')

    def unpublish(self, post:dict) -> dict:
        return self._error('platform_error', 'Unpublish not supported on this platform')

    def get_status(self, post_id:str) -> dict:
        return self._error('platform_error', 'Status check not supported on this platform')

    def format_content(self, content:str) -> dict:
        return self._success(formatted=content)

class SubstackPublisher(PlatformPublisher):

    display_name = 'Substack'
    platform_type = 'newsletter'
    max_length = None

    def is_connected(self) -> bool:
        return True

    def required_env_vars(self) -> list[str]:
        return []

    def publish(self, post:dict) -> dict:
        html = self._markdown_to_html(post.get('content', ''))
        title = post.get('title', 'Untitled')
        full_html = f'<h1>{title}</h1>\n{html}'

        tmp = Path(tempfile.gettempdir()) / f'substack_{post["post_id"]}.html'
        tmp.write_text(full_html, encoding='utf-8')

        return self._success(
            post_id=post['post_id'], platform='substack', title=title,
            file_path=str(tmp), content_length=len(full_html), action='publish',
            message='Substack has no public API. Content formatted as HTML. Copy-paste into editor.',
        )

    def schedule(self, post:dict, scheduled_at:str) -> dict:
        result = self.publish(post)
        if result.get('_success'):
            result['scheduled_at'] = scheduled_at
            result['action'] = 'schedule'
        return result

    def get_status(self, post_id:str) -> dict:
        return self._error('platform_error',
            'Substack has no public API — cannot check publication status.')

    def format_content(self, content:str) -> dict:
        html = self._markdown_to_html(content)
        return self._success(formatted=html, format='html', platform='substack')

    def _markdown_to_html(self, md:str) -> str:
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

    def publish(self, post:dict) -> dict:
        try:
            import tweepy
        except ImportError:
            return self._error('server_error', 'tweepy is not installed. Run: pip install tweepy')

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
            for text in tweets:
                resp = client.create_tweet(text=text, in_reply_to_tweet_id=reply_to)
                tweet_id = resp.data['id']
                posted_ids.append(tweet_id)
                reply_to = tweet_id

            return self._success(
                post_id=post['post_id'], platform='twitter',
                tweet_ids=posted_ids, tweet_count=len(posted_ids),
                thread=len(posted_ids) > 1, action='publish',
            )
        except tweepy.TweepyException as exc:
            return self._error('platform_error', f'Twitter API error: {exc}')

    def schedule(self, post:dict, scheduled_at:str) -> dict:
        return self._error('platform_error',
            'Twitter free/basic API does not support native scheduling.')

    def get_status(self, post_id:str) -> dict:
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
            resp = client.get_tweet(post_id, tweet_fields=['created_at', 'public_metrics'])
            if resp.data:
                return self._success(
                    platform='twitter', tweet_id=post_id,
                    text=resp.data.text, created_at=str(resp.data.created_at),
                    metrics=resp.data.public_metrics, live=True,
                    url=f'https://x.com/i/status/{post_id}',
                )
            return self._error('not_found', f'Tweet not found: {post_id}')
        except tweepy.TweepyException as exc:
            return self._error('platform_error', f'Twitter API error: {exc}')

    def format_content(self, content:str) -> dict:
        tweets = self._split_into_tweets(content)
        return self._success(
            formatted=tweets, format='thread', platform='twitter',
            tweet_count=len(tweets),
        )

    def _split_into_tweets(self, content:str) -> list[str]:
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

    def publish(self, post:dict) -> dict:
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
                    return self._success(
                        post_id=post['post_id'], platform='linkedin',
                        post_urn=post_urn, content_length=len(formatted),
                        action='publish',
                    )
                elif resp.status_code == 401:
                    return self._error('auth_error',
                        'LinkedIn access token expired or invalid.')
                elif resp.status_code == 429:
                    return self._error('rate_limit',
                        'LinkedIn rate limit exceeded. Try again later.')
                else:
                    return self._error('platform_error',
                        f'LinkedIn API error {resp.status_code}: {resp.text}')
        except httpx.HTTPError as exc:
            return self._error('server_error', f'LinkedIn request failed: {exc}')

    def schedule(self, post:dict, scheduled_at:str) -> dict:
        return self._error('platform_error',
            'LinkedIn API does not support native scheduling.')

    def get_status(self, post_id:str) -> dict:
        try:
            import httpx
        except ImportError:
            return self._error('server_error', 'httpx is not installed.')

        try:
            with self._client() as client:
                resp = client.get(f'/posts/{post_id}')
                if resp.status_code == 200:
                    data = resp.json()
                    return self._success(
                        platform='linkedin', post_urn=post_id,
                        lifecycle_state=data.get('lifecycleState', 'unknown'),
                        live=data.get('lifecycleState') == 'PUBLISHED',
                        created_at=data.get('createdAt'),
                    )
                elif resp.status_code == 404:
                    return self._error('not_found', f'LinkedIn post not found: {post_id}')
                else:
                    return self._error('platform_error',
                        f'LinkedIn API error {resp.status_code}: {resp.text}')
        except httpx.HTTPError as exc:
            return self._error('server_error', f'LinkedIn request failed: {exc}')

    def format_content(self, content:str) -> dict:
        formatted = self._format_for_linkedin(content, {})
        return self._success(
            formatted=formatted, format='text', platform='linkedin',
            truncated=len(content) > self.max_length,
        )

    def _format_for_linkedin(self, content:str, metadata:dict) -> str:
        text = re.sub(r'#{1,6}\s+', '', content)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'\1 (\2)', text)

        tags = metadata.get('tags', [])
        if tags:
            hashtags = ' '.join(f'#{tag.replace(" ", "")}' for tag in tags)
            text = f'{text}\n\n{hashtags}'

        if len(text) > self.max_length:
            text = text[:self.max_length - 3] + '...'
        return text

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

    def _build_filename(self, post:dict) -> str:
        date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        slug = self._slugify(post.get('title', 'untitled'))
        prefix = '_eval_' if os.getenv('HUGO_EVAL_MODE') else ''
        return f'{prefix}{date}-{slug}.md'

    def _build_frontmatter(self, post:dict) -> str:
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

    def _git(self, *args:str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ['git', *args],
            cwd=self._repo_path(),
            capture_output=True, text=True, timeout=30,
        )

    def publish(self, post:dict) -> dict:
        posts_dir = self._posts_dir()
        if not posts_dir.exists():
            return self._error('server_error', f'_posts directory not found at {posts_dir}')

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
            return self._error('server_error', f'git push failed: {result.stderr}')

        return self._success(
            post_id=post['post_id'], platform='mt1t',
            filename=filename, file_path=str(filepath), action='publish',
        )

    def schedule(self, post:dict, scheduled_at:str) -> dict:
        drafts_dir = self._drafts_dir()
        drafts_dir.mkdir(parents=True, exist_ok=True)

        filename = self._build_filename(post)
        filepath = drafts_dir / filename

        meta = dict(post.get('metadata', {}))
        meta['publish_date'] = scheduled_at
        post_copy = {**post, 'metadata': meta}

        content = self._build_frontmatter(post_copy) + '\n' + post.get('content', '')
        filepath.write_text(content, encoding='utf-8')

        return self._success(
            post_id=post['post_id'], platform='mt1t',
            filename=filename, file_path=str(filepath),
            scheduled_at=scheduled_at, action='schedule',
        )

    def unpublish(self, post:dict) -> dict:
        posts_dir = self._posts_dir()
        slug = self._slugify(post.get('title', ''))
        matches = list(posts_dir.glob(f'*-{slug}.md'))

        if not matches:
            return self._error('not_found',
                f'No published post matching "{post.get("title", "")}" found in _posts/')

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
            return self._error('server_error', f'git push failed: {result.stderr}')

        return self._success(
            post_id=post['post_id'], platform='mt1t',
            filename=filepath.name, action='unpublish',
        )

    def get_status(self, post_id:str) -> dict:
        from backend.utilities.post_service import PostService
        post_svc = PostService()
        post_result = post_svc.read_metadata(post_id)
        if not post_result.get('_success'):
            return post_result

        slug = self._slugify(post_result.get('title', ''))
        posts_dir = self._posts_dir()
        matches = list(posts_dir.glob(f'*-{slug}.md'))

        if matches:
            filepath = matches[0]
            return self._success(
                platform='mt1t', post_id=post_id,
                filename=filepath.name, file_path=str(filepath), live=True,
            )

        drafts_dir = self._drafts_dir()
        draft_matches = list(drafts_dir.glob(f'*-{slug}.md'))
        if draft_matches:
            return self._success(
                platform='mt1t', post_id=post_id,
                filename=draft_matches[0].name,
                file_path=str(draft_matches[0]),
                live=False, status='draft',
            )

        return self._success(
            platform='mt1t', post_id=post_id,
            live=False, status='not_published',
        )

    def format_content(self, content:str) -> dict:
        return self._success(formatted=content, format='markdown', platform='mt1t')
