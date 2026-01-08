"""知网爬虫 - 高级版（支持无头模式、排序、反爬检测）."""

from __future__ import annotations

import csv
import json
import os
import random
import re
import tempfile
import time
import urllib.parse
from datetime import datetime
from enum import Enum
from typing import Any

from DrissionPage import Chromium, ChromiumOptions

from cnki.browser import ensure_browser, find_chrome_path, setup_virtual_display


class SortOrder(Enum):
    """排序方式枚举."""

    RELEVANCE = ""
    DATE = "PT"
    CITED = "FC"
    DOWNLOAD = "FD"


class AntiCrawlerException(Exception):
    """反爬虫检测异常."""


class CNKICrawlerHeadless:
    """知网爬虫 - 高级版."""

    SEARCH_URL = "https://kns.cnki.net/kns8s/search"

    CAPTCHA_SELECTORS = [
        "#verify-bar-box",
        ".verify-wrap",
        ".captcha-container",
        ".nc-container",
    ]

    def __init__(
        self,
        headless: bool = True,
        browser_path: str | None = None,
        auto_download: bool = True,
        request_delay: float = 2.0,
        max_retries: int = 3,
    ) -> None:
        """初始化爬虫."""
        self.headless = headless
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.virtual_display = None
        self.anti_crawler_triggered = False

        if headless:
            self.virtual_display = setup_virtual_display()

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
            self.options.set_argument("--disable-gpu")

        self.options.set_argument("--remote-allow-origins=*")
        self.options.set_argument("--no-sandbox")
        self.options.set_argument("--disable-dev-shm-usage")
        self.options.set_argument("--disable-blink-features=AutomationControlled")
        self.options.set_argument("--window-size=1920,1080")

        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
        ]
        self.options.set_argument(f"--user-agent={random.choice(user_agents)}")

        self.user_data_dir = tempfile.mkdtemp(prefix="cnki_crawler_headless_")
        self.options.set_user_data_path(self.user_data_dir)
        self.options.auto_port()

        self.browser = None
        self.page = None
        self.results: list[dict[str, Any]] = []

    def start(self) -> bool:
        """启动浏览器."""
        try:
            print("正在启动浏览器...")
            print(f"模式: {'无头' if self.headless else '有头'}")
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

        if self.virtual_display:
            try:
                self.virtual_display.stop()
            except Exception:
                pass

    def check_anti_crawler(self) -> bool:
        """检查是否触发反爬."""
        if not self.page:
            return False

        try:
            for selector in self.CAPTCHA_SELECTORS:
                try:
                    elem = self.page.ele(f"css:{selector}", timeout=0.5)
                    if elem:
                        self.anti_crawler_triggered = True
                        return True
                except Exception:
                    continue

            page_title = self.page.title.lower() if self.page.title else ""
            if any(kw in page_title for kw in ["验证", "captcha", "verify"]):
                self.anti_crawler_triggered = True
                return True

            return False
        except Exception:
            return False

    def _apply_sort_order(self, sort_order: SortOrder) -> bool:
        """通过点击排序按钮应用排序."""
        try:
            print(f"正在应用排序: {sort_order.name}...")

            sort_id_map = {
                SortOrder.RELEVANCE: "FFD",
                SortOrder.DATE: "PT",
                SortOrder.CITED: "CF",
                SortOrder.DOWNLOAD: "DFR",
            }

            target_id = sort_id_map.get(sort_order)
            if not target_id:
                return True

            time.sleep(1)

            # 尝试通过ID点击
            for selector in [f"css:#orderList li#{target_id}", f"css:#{target_id}"]:
                try:
                    sort_btn = self.page.ele(selector, timeout=3)
                    if sort_btn:
                        sort_btn.click()
                        time.sleep(3)
                        print(f"排序已应用: {sort_order.name}")
                        return True
                except Exception:
                    continue

            print(f"⚠️ 未找到排序按钮: {sort_order.name}")
            return False

        except Exception as e:
            print(f"排序失败: {e}")
            return False

    def search(
        self,
        keyword: str,
        max_results: int = 20,
        sort_order: SortOrder = SortOrder.RELEVANCE,
    ) -> list[dict[str, Any]]:
        """搜索知网文章."""
        if not self.page:
            if not self.start():
                return []

        print(f"正在搜索: {keyword}")
        print(f"排序方式: {sort_order.name}")

        encoded_keyword = urllib.parse.quote(keyword)
        search_url = f"{self.SEARCH_URL}?classid=WD0FTY92&kw={encoded_keyword}"
        print(f"搜索URL: {search_url}")

        self.page.get(search_url)
        delay = self.request_delay + random.uniform(0, 1)
        time.sleep(delay)

        if self.check_anti_crawler():
            print("⚠️ 触发反爬")
            return []

        time.sleep(2)

        if sort_order != SortOrder.RELEVANCE:
            self._apply_sort_order(sort_order)

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

            if self.anti_crawler_triggered:
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
                print(f"  [{i + 1}] {title[:50]}... (被引:{cite_count}, 下载:{download_count})")

            except Exception:
                continue

        return results

    def get_article_detail(self, url: str) -> dict[str, Any] | None:
        """获取文章详情."""
        if not self.page:
            self.start()

        if self.anti_crawler_triggered:
            return None

        try:
            if url.startswith("//"):
                url = "https:" + url
            elif not url.startswith("http"):
                url = "https://kns.cnki.net" + url

            self.page.get(url)
            delay = self.request_delay + random.uniform(0, 1)
            time.sleep(delay)

            if self.check_anti_crawler():
                return None

            detail: dict[str, Any] = {}

            title_elem = self.page.ele("css:.wx-tit h1", timeout=5) or self.page.ele("css:h1.title", timeout=3)
            detail["title"] = title_elem.text.strip() if title_elem else ""

            author_elem = self.page.ele("css:.author", timeout=3)
            detail["author"] = author_elem.text.strip() if author_elem else ""

            org_elem = self.page.ele("css:.orgn", timeout=3)
            detail["organization"] = org_elem.text.strip() if org_elem else ""

            abstract_elem = self.page.ele("css:.abstract-text", timeout=3) or self.page.ele("css:#ChDivSummary", timeout=3)
            detail["abstract"] = abstract_elem.text.strip() if abstract_elem else ""

            keywords_elem = self.page.ele("css:.keywords", timeout=3)
            detail["keywords"] = keywords_elem.text.strip() if keywords_elem else ""

            page_text = self.page.html
            doi_match = re.search(r"DOI[：:]\s*(10\.\d{4,}/[^\s<]+)", page_text)
            detail["doi"] = doi_match.group(1) if doi_match else ""

            detail["url"] = url
            detail["crawl_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            return detail

        except AntiCrawlerException:
            raise
        except Exception as e:
            print(f"获取详情失败: {e}")
            return None

    def search_and_crawl(
        self,
        keyword: str,
        max_results: int = 20,
        get_details: bool = True,
        sort_order: SortOrder = SortOrder.RELEVANCE,
    ) -> list[dict[str, Any]]:
        """搜索并抓取文章."""
        try:
            results = self.search(keyword, max_results, sort_order)

            if not get_details:
                return results

            if self.anti_crawler_triggered:
                return results

            detailed_results = []
            for i, result in enumerate(results):
                if self.anti_crawler_triggered:
                    detailed_results.extend(results[i:])
                    break

                print(f"\n获取详情 {i + 1}/{len(results)}...")

                if result.get("link"):
                    try:
                        detail = self.get_article_detail(result["link"])
                        if detail:
                            merged = {**result, **detail}
                            if result.get("cite_count", "0") != "0":
                                merged["cite_count"] = result["cite_count"]
                            if result.get("download_count", "0") != "0":
                                merged["download_count"] = result["download_count"]
                            detailed_results.append(merged)
                        else:
                            detailed_results.append(result)
                    except AntiCrawlerException:
                        detailed_results.append(result)
                        detailed_results.extend(results[i + 1 :])
                        break
                else:
                    detailed_results.append(result)

                time.sleep(self.request_delay)

            self.results = detailed_results
            return detailed_results

        except AntiCrawlerException as e:
            print(f"⚠️ 触发反爬: {e}")
            return self.results

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