"""
Builds eBay RSS feed URLs from search query strings.
"""

import urllib.parse
from app.config import get_settings, SEARCH_QUERIES, build_feed_url


def get_all_feed_urls() -> list[dict[str, str]]:
    """
    Return a list of dicts with 'query' and 'url' for every configured search query.
    """
    return [
        {"query": q, "url": build_feed_url(q)}
        for q in SEARCH_QUERIES
    ]
