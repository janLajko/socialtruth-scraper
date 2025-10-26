#!/usr/bin/env python3
"""
Fetch the latest Truth Social post by @realDonaldTrump, send it to a Lark
incoming webhook, and skip delivery if the post was already sent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://truthsocial.com"
API_BASE_URL = f"{BASE_URL}/api"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})


def lookup_account(username: str) -> Dict[str, Any]:
    """Resolve a Truth Social username to an account payload."""
    resp = session.get(
        f"{API_BASE_URL}/v1/accounts/lookup",
        params={"acct": username},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_latest_status(account_id: str) -> Optional[Dict[str, Any]]:
    """Fetch only the most recent status for an account id."""
    resp = session.get(
        f"{API_BASE_URL}/v1/accounts/{account_id}/statuses",
        params={"exclude_replies": "true", "limit": 1},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return data[0] if data else None


def simplify(status: Dict[str, Any]) -> Dict[str, Any]:
    """Convert the verbose status payload into a compact structure."""
    content_html = status.get("content", "")
    text = BeautifulSoup(content_html, "html.parser").get_text(separator=" ").strip()

    simplified: Dict[str, Any] = {
        "id": str(status.get("id", "")),
        "url": status.get("url"),
        "created_at": status.get("created_at"),
        "language": status.get("language"),
        "text": text or "[Post contains only media or formatting]",
        "raw_html": content_html,
        "replies_count": status.get("replies_count"),
        "reblogs_count": status.get("reblogs_count"),
        "favorites_count": status.get("favourites_count"),
    }

    media_items = []
    for media in status.get("media_attachments", []):
        media_items.append(
            {
                "id": media.get("id"),
                "type": media.get("type"),
                "url": media.get("url") or media.get("remote_url"),
                "preview_url": media.get("preview_url"),
            }
        )
    if media_items:
        simplified["media"] = media_items

    if status.get("reblog"):
        simplified["is_reblog"] = True
        original = status["reblog"]
        simplified["original_author"] = original.get("account", {}).get("acct")
        simplified["original_url"] = original.get("url")
        original_html = original.get("content", "")
        simplified["original_text"] = BeautifulSoup(
            original_html, "html.parser"
        ).get_text(separator=" ").strip()

    return simplified


def load_last_sent(state_path: Path) -> Optional[str]:
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        value = data.get("last_id")
        return str(value) if value is not None else None
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError):
        return None


def save_last_sent(state_path: Path, status_id: str) -> None:
    try:
        if state_path.parent and not state_path.parent.exists():
            state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"last_id": status_id}), encoding="utf-8")
    except OSError:
        pass


def build_message(post: Dict[str, Any], username: str) -> str:
    segments = [f"Truth Social update from @{username}", "", post.get("text", "")]

    media_items = post.get("media") or []
    if media_items:
        segments.append("")
        segments.append("Media:")
        for item in media_items:
            label = item.get("type", "media")
            url = item.get("url") or item.get("preview_url")
            if url:
                segments.append(f"- {label}: {url}")

    url = post.get("url")
    if url:
        segments.append("")
        segments.append(f"Link: {url}")

    return "\n".join(segment for segment in segments if segment)


def send_to_lark(post: Dict[str, Any], webhook_url: str, username: str) -> None:
    message = build_message(post, username)
    resp = requests.post(
        webhook_url,
        json={"msg_type": "text", "content": {"text": message}},
        headers={"Content-Type": "application/json"},
        timeout=20,
    )
    resp.raise_for_status()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Send the latest Truth Social post to a Lark webhook."
    )
    parser.add_argument(
        "--webhook",
        required=True,
        help="Lark (Feishu) incoming webhook URL.",
    )
    parser.add_argument(
        "--state-file",
        default="truthsocial_last_id.json",
        help="Path to the JSON file storing the last sent post id.",
    )
    parser.add_argument(
        "--username",
        default="realDonaldTrump",
        help="Truth Social username without the leading @ (default: realDonaldTrump).",
    )
    args = parser.parse_args(argv)

    try:
        account = lookup_account(args.username)
        latest = fetch_latest_status(str(account["id"]))
    except requests.RequestException as exc:
        print(f"Error fetching posts: {exc}", file=sys.stderr)
        return 1

    if not latest:
        print("No posts returned for the specified user.")
        return 0

    post = simplify(latest)
    state_path = Path(args.state_file)
    last_sent_id = load_last_sent(state_path)

    if last_sent_id == post["id"]:
        print("Latest post already sent to Lark; nothing to do.")
        return 0

    try:
        send_to_lark(post, args.webhook, args.username)
    except requests.RequestException as exc:
        print(f"Failed to send message to Lark: {exc}", file=sys.stderr)
        return 1

    save_last_sent(state_path, post["id"])
    print(f"Delivered post {post['id']} to Lark.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
