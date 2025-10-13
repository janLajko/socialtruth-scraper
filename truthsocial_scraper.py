#!/usr/bin/env python3
"""
Fetch the latest public posts from a Truth Social profile.

This script uses the same client credentials that the official web client ships
with to obtain a short-lived application token and then calls the public API.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import os
from html import unescape
from typing import Any, Dict, List, Optional

from curl_cffi import requests

BASE_URL = "https://truthsocial.com"
API_BASE_URL = f"{BASE_URL}/api"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

# These values are embedded in the production Truth Social web bundle.
CLIENT_ID = "9X1Fdd-pxNsAgEDNi_SfhJWi8T-vLuV2WVzKIbkTCw4"
CLIENT_SECRET = "ozF8jzI4968oTKFkEnsBC-UbLPCdrSv0MkXGQu2o_-M"

TAG_RE = re.compile(r"<[^>]+>")


class TruthSocialClient:
    """Lightweight wrapper around the Truth Social REST API."""

    def __init__(self, token: str):
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "User-Agent": USER_AGENT,
            }
        )

    @classmethod
    def from_client_credentials(cls) -> "TruthSocialClient":
        """Create a client by exchanging the public client credentials for a token."""
        try:
            resp = requests.post(
                f"{BASE_URL}/oauth/token",
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "client_credentials",
                    "scope": "read",
                },
                impersonate="chrome120",
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
        except requests.RequestsError as exc:
            raise RuntimeError(f"Failed to obtain Truth Social token: {exc}") from exc

        data: Dict[str, Any] = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Truth Social token response did not contain access_token")
        return cls(token)

    def _get(self, path: str, *, params: Optional[Dict[str, Any]] = None) -> Any:
        """Perform a GET request against the API with the required impersonation."""
        try:
            resp = self._session.get(
                f"{API_BASE_URL}{path}",
                params=params,
                impersonate="chrome120",
            )
            resp.raise_for_status()
        except requests.RequestsError as exc:
            raise RuntimeError(f"Truth Social API request failed: {exc}") from exc
        return resp.json()

    def lookup_user(self, username: str) -> Dict[str, Any]:
        """Retrieve basic profile information for a username."""
        return self._get("/v1/accounts/lookup", params={"acct": username})

    def fetch_statuses(
        self,
        user_id: str,
        *,
        limit: int = 1,
        include_replies: bool = False,
    ) -> List[Dict[str, Any]]:
        """Fetch the most recent statuses for a user id."""
        params: Dict[str, Any] = {"limit": max(1, min(limit, 40))}
        if not include_replies:
            params["exclude_replies"] = "true"
        return self._get(f"/v1/accounts/{user_id}/statuses", params=params)


def html_to_text(html: str) -> str:
    """Convert Truth Social's HTML content payload into readable text."""
    normalized = (
        html.replace("<br />", "\n")
        .replace("<br>", "\n")
        .replace("</p>", "\n")
        .replace("<p>", "\n")
    )
    text = TAG_RE.sub("", normalized)
    lines = (line.strip() for line in text.splitlines())
    cleaned = "\n".join(filter(None, lines))
    return unescape(cleaned).strip()


def simplify_status(status: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce the verbose Mastodon status payload to the essentials."""
    media_items = [
        {
            "id": media.get("id"),
            "type": media.get("type"),
            "url": media.get("url") or media.get("remote_url"),
            "preview_url": media.get("preview_url"),
        }
        for media in status.get("media_attachments", [])
    ]

    simplified = {
        "id": status.get("id"),
        "url": status.get("url"),
        "created_at": status.get("created_at"),
        "language": status.get("language"),
        "text": html_to_text(status.get("content", "")),
        "raw_html": status.get("content", ""),
        "replies_count": status.get("replies_count"),
        "reblogs_count": status.get("reblogs_count"),
        "favorites_count": status.get("favourites_count"),
        "media": [item for item in media_items if item["url"]],
    }

    if status.get("reblog"):
        original = status["reblog"]
        simplified["is_reblog"] = True
        simplified["original_author"] = original.get("account", {}).get("acct")
        simplified["original_url"] = original.get("url")
        simplified["original_text"] = html_to_text(original.get("content", ""))

    return simplified


def fetch_latest_truths(
    username: str,
    *,
    limit: int = 1,
    include_replies: bool = False,
) -> List[Dict[str, Any]]:
    """Fetch and simplify the latest posts for a Truth Social username."""
    client = TruthSocialClient.from_client_credentials()
    profile = client.lookup_user(username)
    statuses = client.fetch_statuses(
        profile["id"], limit=limit, include_replies=include_replies
    )
    return [simplify_status(status) for status in statuses[:limit]]


def send_to_lark(
    posts: List[Dict[str, Any]],
    webhook_url: str,
    *,
    username: str,
) -> None:
    """Send the latest post to a Lark (Feishu) incoming webhook."""
    if not posts:
        print("No posts to send to Lark.")
        return

    latest = posts[0]
    text_body = latest.get("text") or "[Post contains only media or formatting]"

    segments = [
        f"Truth Social update from @{username}",
        "",
        text_body,
    ]

    media = latest.get("media") or []
    if media:
        segments.append("")
        segments.append("Media:")
        for item in media:
            label = item.get("type", "media")
            url = item.get("url") or item.get("preview_url")
            if url:
                segments.append(f"- {label}: {url}")

    post_url = latest.get("url")
    if post_url:
        segments.append("")
        segments.append(f"Link: {post_url}")

    message = "\n".join(segment for segment in segments if segment is not None)

    try:
        resp = requests.post(
            webhook_url,
            json={"msg_type": "text", "content": {"text": message}},
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
    except requests.RequestsError as exc:
        raise RuntimeError(f"Failed to deliver message to Lark: {exc}") from exc

    print("Sent latest post to Lark successfully.")


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch the latest posts from a Truth Social profile."
    )
    parser.add_argument(
        "-u",
        "--username",
        default="realDonaldTrump",
        help="Truth Social username without the leading @ (default: realDonaldTrump)",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=1,
        help="Number of recent posts to fetch (1-40, default: 1)",
    )
    parser.add_argument(
        "--include-replies",
        action="store_true",
        help="Include replies in the results (default: false)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON output.",
    )
    parser.add_argument(
        "--lark-webhook",
        help="Feishu/Lark incoming webhook URL. "
        "If omitted, falls back to the environment variable named by --lark-webhook-env.",
    )
    parser.add_argument(
        "--lark-webhook-env",
        default="LARK_WEBHOOK_URL",
        help="Environment variable to read the webhook URL from when --lark-webhook is empty "
        "(default: LARK_WEBHOOK_URL). Use an empty string to disable env lookup.",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    try:
        posts = fetch_latest_truths(
            args.username,
            limit=args.limit,
            include_replies=args.include_replies,
        )

        webhook_url = args.lark_webhook
        if not webhook_url and args.lark_webhook_env:
            webhook_url = os.getenv(args.lark_webhook_env)
        if webhook_url:
            send_to_lark(posts, webhook_url, username=args.username)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.pretty:
        print(json.dumps(posts, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(posts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
