"""
connect_apis.py — Smoke test for external service connectivity.

Usage:
    python connect_apis.py --service github
    python connect_apis.py --service slack [--channel general]
    python connect_apis.py --service linkedin
    python connect_apis.py --service substack

Credentials are read from shared/.keys (KEY=value format, one per line).
Falls back to env vars if a key isn't in the file.
See shared/gather_tokens.md for how to obtain each token.

Packages:
    github    — requests
    slack     — slack-sdk
    linkedin  — requests
    substack  — python-substack, requests
"""

import argparse
import os
import pathlib
import sys
import urllib.parse
import xml.etree.ElementTree as ET

import requests


SERVICES = ["github", "slack", "linkedin", "substack"]
KEYS_FILE = pathlib.Path(__file__).parent / ".keys"


def _load_keys():
    """Parse shared/.keys into a dict. Skips blank lines and comments."""
    keys = {}
    if not KEYS_FILE.exists():
        return keys
    for line in KEYS_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip()
        if name and value:
            keys[name] = value
    return keys


_KEYS = _load_keys()


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

def test_github():
    token = _require_env("GITHUB_TOKEN")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    print("Fetching 5 most recently updated repos...\n")
    resp = requests.get(
        "https://api.github.com/user/repos",
        headers=headers,
        params={"sort": "updated", "direction": "desc", "per_page": 5},
    )
    if resp.status_code != 200:
        _fail(f"GitHub API returned {resp.status_code}: "
              f"{resp.json().get('message', resp.text)}")

    repos = resp.json()
    if not repos:
        print("No repos found. Token may lack repo access permissions.")
    else:
        for repo in repos:
            vis = "private" if repo["private"] else "public"
            print(f"  {repo['full_name']}  ({vis})  updated {repo['updated_at']}")

    print()
    rate_resp = requests.get("https://api.github.com/rate_limit", headers=headers)
    if rate_resp.status_code == 200:
        core = rate_resp.json()["resources"]["core"]
        print(f"Rate limit: {core['remaining']}/{core['limit']} remaining")

    print("\nGitHub connection OK.")


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------

def test_slack(channel_name=None):
    token = _require_env("SLACK_BOT_TOKEN")

    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    client = WebClient(token=token)

    print("Fetching public channels...\n")
    try:
        result = client.conversations_list(
            types="public_channel", limit=5, exclude_archived=True,
        )
    except SlackApiError as e:
        _fail(f"Slack API error: {e.response['error']}")

    channels = result["channels"]
    if not channels:
        print("No public channels found.")
        return

    for ch in channels:
        print(f"  #{ch['name']}  ({ch.get('num_members', '?')} members)")

    # Resolve target channel
    target = None
    if channel_name:
        channel_name = channel_name.lstrip("#")
        for ch in channels:
            if ch["name"] == channel_name:
                target = ch
                break
        if not target:
            try:
                all_ch = client.conversations_list(
                    types="public_channel", limit=200, exclude_archived=True,
                )
                for ch in all_ch["channels"]:
                    if ch["name"] == channel_name:
                        target = ch
                        break
            except SlackApiError:
                pass
        if not target:
            _fail(f"Channel '#{channel_name}' not found.")
    else:
        target = channels[0]

    print(f"\n3 most recent messages in #{target['name']}:\n")
    try:
        history = client.conversations_history(channel=target["id"], limit=3)
    except SlackApiError as e:
        _fail(f"Slack API error: {e.response['error']}\n"
              "The bot may need to be invited to this channel first.")

    messages = history["messages"]
    if not messages:
        print("  (no messages)")
    else:
        for msg in messages:
            user = msg.get("user", "bot")
            text = msg.get("text", "(no text)")
            if len(text) > 120:
                text = text[:120] + "..."
            print(f"  [{user}] {text}")

    print("\nSlack connection OK.")


# ---------------------------------------------------------------------------
# LinkedIn
# ---------------------------------------------------------------------------

LINKEDIN_REDIRECT_URI = "http://localhost:8000/callback"

def test_linkedin():
    client_id = _require_env("LINKEDIN_CLIENT_ID")
    client_secret = _require_env("LINKEDIN_CLIENT_SECRET")

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "scope": "openid profile email",
        "state": "smoke_test",
    }
    auth_link = (
        f"https://www.linkedin.com/oauth/v2/authorization?"
        f"{urllib.parse.urlencode(params)}"
    )

    print("Open this URL in your browser to authorize:\n")
    print(f"  {auth_link}\n")
    print("After authorizing, you'll be redirected to a URL like:")
    print("  http://localhost:8000/callback?code=XXXX&state=smoke_test\n")
    print("Copy the 'code' value from the URL.")

    code = input("\nPaste the authorization code here: ").strip()
    if not code:
        _fail("No code provided.")

    print("\nExchanging code for access token...")
    token_resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": LINKEDIN_REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if token_resp.status_code != 200:
        _fail(f"Token exchange failed ({token_resp.status_code}): {token_resp.text}")

    access_token = token_resp.json().get("access_token")
    if not access_token:
        _fail(f"No access_token in response: {token_resp.json()}")

    expires_in = token_resp.json().get("expires_in", "unknown")
    print(f"Access token obtained (expires in {expires_in}s)")

    print("\nFetching profile...\n")
    profile_resp = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if profile_resp.status_code != 200:
        _fail(f"Profile fetch failed ({profile_resp.status_code}): "
              f"{profile_resp.text}")

    profile = profile_resp.json()
    print(f"  Name:  {profile.get('name', 'N/A')}")
    print(f"  Email: {profile.get('email', 'N/A')}")

    print("\nLinkedIn connection OK.")
    print("\nNext steps:")
    print("  - To post to your feed, request 'Share on LinkedIn' product approval")
    print("  - Then add w_member_social scope and use the Posts API")


# ---------------------------------------------------------------------------
# Substack
# ---------------------------------------------------------------------------

def test_substack():
    sid = _require_env("SUBSTACK_SID")
    lli = _require_env("SUBSTACK_LLI")

    try:
        from substack import Api
        from substack.post import Post
    except ImportError:
        _fail("python-substack is not installed. Run: pip install python-substack")

    cookies_string = f"substack.sid={sid}; substack.lli={lli}"

    # List publications
    print("Fetching your publications...\n")
    try:
        api = Api(cookies_string=cookies_string)
        publications = api.get_user_publications()
    except Exception as e:
        _fail(f"Failed to connect: {e}\n"
              "Cookies may have expired. Re-export from browser.")

    if not publications:
        print("No publications found.")
        print("Create a Substack newsletter first, then re-run.")
        return

    for pub in publications:
        name = pub.get("name", "Untitled")
        subdomain = pub.get("subdomain", "?")
        print(f"  {name}  (https://{subdomain}.substack.com)")

    pub = publications[0]
    subdomain = pub.get("subdomain")
    pub_url = f"https://{subdomain}.substack.com"
    api = Api(cookies_string=cookies_string, publication_url=pub_url)

    # Fetch 3 most recent posts via RSS
    print(f"\n3 most recent posts from {subdomain}:\n")
    try:
        rss_resp = requests.get(f"{pub_url}/feed", timeout=10)
        if rss_resp.status_code == 200:
            root = ET.fromstring(rss_resp.content)
            items = root.findall(".//item")[:3]
            if not items:
                print("  (no posts found)")
            for item in items:
                title = item.findtext("title", "Untitled")
                pub_date = item.findtext("pubDate", "Unknown date")
                link = item.findtext("link", "")
                print(f"  {title}")
                print(f"    {pub_date}  {link}")
        else:
            print(f"  Could not fetch RSS feed ({rss_resp.status_code})")
    except Exception as e:
        print(f"  Could not fetch recent posts: {e}")

    # Create a test draft (NOT published)
    print("\nCreating test draft...\n")
    try:
        user_id = api.get_user_id()
        post = Post(
            title="API Test \u2014 Delete Me",
            subtitle="Automated connectivity test",
            user_id=user_id,
            audience="only_free",
        )
        post.add({"type": "paragraph", "content": "Testing API connectivity."})
        draft = api.post_draft(post.get_draft())
        draft_id = draft.get("id", "unknown")
        print(f"  Draft created (id: {draft_id})")
        print("  This draft is NOT published. Delete it from your dashboard.")
    except Exception as e:
        _fail(f"Draft creation failed: {e}\n"
              "Cookies may have expired, or publication setup is incomplete.")

    print("\nSubstack connection OK.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_env(name):
    value = _KEYS.get(name) or os.environ.get(name)
    if not value:
        print(f"ERROR: {name} is not set.")
        print(f"Add it to {KEYS_FILE} or set it as an env var.")
        print("See shared/gather_tokens.md for setup instructions.")
        sys.exit(1)
    return value


def _fail(message):
    print(f"ERROR: {message}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Smoke test connectivity to external services.",
    )
    parser.add_argument(
        "--service", required=True, choices=SERVICES,
        help="Which service to test",
    )
    parser.add_argument(
        "--channel", default=None,
        help="(slack only) Channel name to read messages from",
    )
    args = parser.parse_args()

    dispatch = {
        "github": lambda: test_github(),
        "slack": lambda: test_slack(args.channel),
        "linkedin": lambda: test_linkedin(),
        "substack": lambda: test_substack(),
    }
    dispatch[args.service]()


if __name__ == "__main__":
    main()
