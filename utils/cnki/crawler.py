"""知网爬虫 - 基础版（有头模式）."""

from __future__ import annotations

import csv
import json
import os
import re
import tempfile
import time
from datetime import datetime
from typing import Any

from DrissionPage import Chromium, ChromiumOptions

from cnki.browser import ensure_browser, find_chrome_path


class CNKICrawler:
    """知网爬虫类 - 基础版."""

    SEARCH_URL = "https://www.cnki.net/"

    def __init__(
        self,
        headless: bool = False,
        browser_path: str | None = None,
        auto_download: bool = True,
    ) -> None:
        """初始化爬虫."""
        self.options = ChromiumOptions()

        if browser_path:
            self.options.set_browser_path(browser_path)
        elif auto_download:
            auto_path = ensure_browser()
            if auto_path:
                print(f"使用浏览器: {auto_path}")
                self.options.set_browser_path(auto_path)
        else:
            auto_path = find_chrome_path()
            if auto_path:
                self.options.set_browser_path(auto_path)

        if headless:
            self.options.headless()

        self.options.set_argument("--remote-allow-origins=*")
        self.options.set_argument("--no-sandbox")
        self.options.set_argument("--disable-dev-shm-usage")

        self.user_data_dir = tempfile.mkdtemp(prefix="cnki_crawler_")
        self.options.set_user_data_path(self.user_data_dir)
        self.options.auto_port()

        self.browser = None
        self.page = None
        self.results: list[dict[str, Any]] = []

    def start(self) -> bool:
        """启动浏览器."""
        try:
            print("正在启动浏览器...")
            self.browser = Chromium(self.options)
            time.sleep(3)
            self.page = self.browser.latest_tab
            if self.page:
                print("浏览器已启动")
                return True
            return False
        except Exception as e:
            print(f"启动失败: {e}")
            return False

    def close(self) -> None:
        """关闭浏览器."""
        if self.browser:
            try:
                self.browser.quit()
                print("浏览器已关闭")
            except Exception:
                pass
            finally:
                self.browser = None
                self.page = None

        if hasattr(self, "user_data_dir") and self.user_data_dir:
            import shutil
            shutil.rmtree(self.user_data_dir, ignore_errors=True)

    def search(self, keyword: str, max_results: int = 20) -> list[dict[str, Any]]:
        """搜索知网文章."""
        if not self.page:
            self.start()

        print(f"正在搜索: {keyword}")
        search_url = f"https://kns.cnki.net/kns8s/search?classid=WD0FTY92&kw={keyword}"
        self.page.get(search_url)
        time.sleep(3)

        return self._parse_search_results(max_results)

    def _parse_search_results(self, max_results: int) -> list[dict[str, Any]]:
        """解析搜索结果."""
        results = []
        result_items = self.page.eles("css:.result-table-list tbody tr", timeout=10)

        if not result_items:
            result_items = self.page.eles("css:#gridTable tbody tr", timeout=5)

        print(f"找到 {len(result_items)} 条结果")

        for i, item in enumerate(result_items):
            if i >= max_results:
                break

            try:
                title_elem = item.ele("css:.name a", timeout=2) or item.ele("css:td.name a", timeout=1)
                if not title_elem:
                    continue

                title = title_elem.text.strip()
                link = title_elem.attr("href")

                author_elem = item.ele("css:.author", timeout=1) or item.ele("css:td.author", timeout=1)
                author = author_elem.text.strip() if author_elem else ""

                source_elem = item.ele("css:.source", timeout=1) or item.ele("css:td.source", timeout=1)
                source = source_elem.text.strip() if source_elem else ""

                date_elem = item.ele("css:.date", timeout=1) or item.ele("css:td.date", timeout=1)
                pub_date = date_elem.text.strip() if date_elem else ""

                # 被引量和下载量
                cite_count = "0"
                download_count = "0"
                try:
                    tds = item.eles("css:td")
                    if len(tds) >= 7:
                        cite_text = tds[6].text.strip()
                        if cite_text.isdigit():
                            cite_count = cite_text
                    if len(tds) >= 8:
                        dl_text = tds[7].text.strip()
                        if dl_text.isdigit():
                            download_count = dl_text
                except Exception:
                    pass

                results.append({
                    "title": title,
                    "link": link,
                    "author": author,
                    "source": source,
                    "pub_date": pub_date,
                    "cite_count": cite_count,
                    "download_count": download_count,
                })
                print(f"  [{i + 1}] {title[:50]}... (被引:{cite_count})")

            except Exception:
                continue

        return results

    def get_article_detail(self, url: str) -> dict[str, Any] | None:
        """获取文章详情."""
        if not self.page:
            self.start()

        try:
            if url.startswith("//"):
                url = "https:" + url
            elif not url.startswith("http"):
                url = "https://kns.cnki.net" + url

            self.page.get(url)
            time.sleep(2)

            detail: dict[str, Any] = {}

            # 标题
            title_elem = self.page.ele("css:.wx-tit h1", timeout=5) or self.page.ele("css:h1.title", timeout=3)
            detail["title"] = title_elem.text.strip() if title_elem else ""

            # 作者
            author_elem = self.page.ele("css:.author", timeout=3)
            detail["author"] = author_elem.text.strip() if author_elem else ""

            # 摘要
            abstract_elem = self.page.ele("css:.abstract-text", timeout=3) or self.page.ele("css:#ChDivSummary", timeout=3)
            detail["abstract"] = abstract_elem.text.strip() if abstract_elem else ""

            # 关键词
            keywords_elem = self.page.ele("css:.keywords", timeout=3)
            detail["keywords"] = keywords_elem.text.strip() if keywords_elem else ""

            # DOI
            page_text = self.page.html
            doi_match = re.search(r"DOI[：:]\s*(10\.\d{4,}/[^\s<]+)", page_text)
            detail["doi"] = doi_match.group(1) if doi_match else ""

            detail["url"] = url
            detail["crawl_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            return detail

        except Exception as e:
            print(f"获取详情失败: {e}")
            return None

    def search_and_crawl(
        self,
        keyword: str,
        max_results: int = 20,
        get_details: bool = True,
    ) -> list[dict[str, Any]]:
        """搜索并抓取文章."""
        results = self.search(keyword, max_results)

        if not get_details:
            return results

        detailed_results = []
        for i, result in enumerate(results):
            print(f"\n获取详情 {i + 1}/{len(results)}...")
            if result.get("link"):
                detail = self.get_article_detail(result["link"])
                if detail:
                    merged = {**result, **detail}
                    if result.get("cite_count", "0") != "0":
                        merged["cite_count"] = result["cite_count"]
                    detailed_results.append(merged)
                else:
                    detailed_results.append(result)
            else:
                detailed_results.append(result)
            time.sleep(1)

        self.results = detailed_results
        return detailed_results

    def save_to_json(self, filename: str | None = None, data: list[dict] | None = None) -> None:
        """保存为JSON."""
        if data is None:
            data = self.results
        if not data:
            return

        if filename is None:
            filename = f"cnki_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"已保存: {filepath}")

    def save_to_csv(self, filename: str | None = None, data: list[dict] | None = None) -> None:
        """保存为CSV."""
        if data is None:
            data = self.results
        if not data:
            return

        if filename is None:
            filename = f"cnki_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)

        fieldnames = sorted({k for item in data for k in item})
        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        print(f"已保存: {filepath}")