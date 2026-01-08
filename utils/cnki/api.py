#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知网爬虫API封装.

提供简单易用的函数接口，可自定义参数搜索知网文献。
"""

from __future__ import annotations

import argparse
import json
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


class SortOrder(Enum):
    """排序方式枚举."""

    RELEVANCE = "relevance"
    DATE = "date"
    CITED = "cited"
    DOWNLOAD = "download"


ALL_FIELDS: list[str] = [
    "title", "authors", "source", "date", "cite_count", "download_count",
    "abstract", "keywords", "doi", "url", "dbcode", "dbname", "filename",
    "fund", "first_author", "institution",
]


def search_cnki(
    keyword: str,
    max_results: int = 10,
    sort_order: str | SortOrder = SortOrder.RELEVANCE,
    headless: bool = True,
    fields: Sequence[str] | None = None,
    get_details: bool = True,
    browser_path: str | None = None,
) -> list[dict[str, Any]]:
    """搜索知网文献."""
    from cnki.crawler_headless import CNKICrawlerHeadless
    from cnki.crawler_headless import SortOrder as CrawlerSortOrder

    if isinstance(sort_order, str):
        sort_map = {
            "relevance": CrawlerSortOrder.RELEVANCE,
            "date": CrawlerSortOrder.DATE,
            "cited": CrawlerSortOrder.CITED,
            "download": CrawlerSortOrder.DOWNLOAD,
        }
        crawler_sort = sort_map.get(sort_order.lower(), CrawlerSortOrder.RELEVANCE)
    elif isinstance(sort_order, SortOrder):
        sort_map = {
            SortOrder.RELEVANCE: CrawlerSortOrder.RELEVANCE,
            SortOrder.DATE: CrawlerSortOrder.DATE,
            SortOrder.CITED: CrawlerSortOrder.CITED,
            SortOrder.DOWNLOAD: CrawlerSortOrder.DOWNLOAD,
        }
        crawler_sort = sort_map.get(sort_order, CrawlerSortOrder.RELEVANCE)
    else:
        crawler_sort = CrawlerSortOrder.RELEVANCE

    crawler = CNKICrawlerHeadless(headless=headless, browser_path=browser_path)

    try:
        if get_details:
            results = crawler.search_and_crawl(
                keyword=keyword,
                max_results=max_results,
                sort_order=crawler_sort,
                get_details=True,
            )
        else:
            results = crawler.search(
                keyword=keyword,
                max_results=max_results,
                sort_order=crawler_sort,
            )

        if fields:
            return [{field: article.get(field) for field in fields} for article in results]
        return results
    finally:
        crawler.close()


def search_cnki_simple(
    keyword: str,
    max_results: int = 10,
    sort_by: str = "relevance",
) -> list[dict[str, Any]]:
    """简化版搜索函数."""
    return search_cnki(keyword=keyword, max_results=max_results, sort_order=sort_by)


def get_article_info(
    keyword: str,
    index: int = 0,
    headless: bool = True,
) -> dict[str, Any] | None:
    """获取单篇文章的详细信息."""
    results = search_cnki(keyword=keyword, max_results=index + 1, headless=headless)
    return results[index] if len(results) > index else None


def main() -> None:
    """命令行入口函数."""
    parser = argparse.ArgumentParser(description="知网文献搜索")
    parser.add_argument("keyword", help="搜索关键词")
    parser.add_argument("-n", "--max-results", type=int, default=10)
    parser.add_argument("-s", "--sort", choices=["relevance", "date", "cited", "download"], default="relevance")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("-f", "--fields", nargs="+")
    parser.add_argument("--no-details", action="store_true")
    parser.add_argument("-o", "--output")

    args = parser.parse_args()

    print(f"搜索: {args.keyword} | 数量: {args.max_results} | 排序: {args.sort}")

    results = search_cnki(
        keyword=args.keyword,
        max_results=args.max_results,
        sort_order=args.sort,
        headless=not args.headed,
        fields=args.fields,
        get_details=not args.no_details,
    )

    print(f"\n找到 {len(results)} 条结果:\n")
    for i, article in enumerate(results, 1):
        print(f"{i}. {article.get('title', 'N/A')}")
        if article.get("cite_count"):
            print(f"   被引: {article['cite_count']}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"已保存: {args.output}")


if __name__ == "__main__":
    main()