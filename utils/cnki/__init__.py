"""知网爬虫包.

提供知网文献搜索和抓取功能。

使用示例:
    from cnki import search_cnki, SortOrder

    # 基本搜索
    results = search_cnki("深度学习")

    # 按被引量排序
    results = search_cnki("机器学习", sort_order="cited", max_results=20)
"""

from cnki.api import (
    ALL_FIELDS,
    SortOrder,
    get_article_info,
    search_cnki,
    search_cnki_simple,
)
from cnki.crawler import CNKICrawler
from cnki.crawler_headless import CNKICrawlerHeadless
from cnki.crawler_headless import SortOrder as CrawlerSortOrder

__all__ = [
    # API
    "search_cnki",
    "search_cnki_simple",
    "get_article_info",
    "SortOrder",
    "ALL_FIELDS",
    # 爬虫类
    "CNKICrawler",
    "CNKICrawlerHeadless",
    "CrawlerSortOrder",
]

__version__ = "1.0.0"