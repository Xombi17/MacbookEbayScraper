"""
Builds eBay RSS feed URLs from search query strings.
"""

import urllib.parse
from app.config import get_settings, SEARCH_QUERIES, EBAY_RSS_TEMPLATE


def build_rss_url(query: str) -> str:
    """
    Encode a search query and return a valid eBay RSS feed URL.

    Example:
        build_rss_url("MacBook Pro M1 Max 64GB")
        → "https://www.ebay.com/sch/i.html?_nkw=MacBook+Pro+M1+Max+64GB&_sop=10&_rss=1"
    """
    encoded = urllib.parse.quote_plus(query)
    return EBAY_RSS_TEMPLATE.format(query=encoded)


def get_all_feed_urls() -> list[dict[str, str]]:
    """
    Return a list of dicts with 'query' and 'url' for every configured search query.
    """
    return [
        {"query": q, "url": build_rss_url(q)}
        for q in SEARCH_QUERIES
    ]
