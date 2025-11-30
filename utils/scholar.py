"""
学术搜索工具 (异步版本)

支持：
- ArXiv 搜索
- Semantic Scholar 搜索
"""

import asyncio

import aiohttp
import xmltodict

# ================= 代码测试配置区域 =================
# 你的 Cloudflare Worker 地址
WORKER_URL = "https://scholar.quirkymeowcorner.fun"

# 等收到邮件后，把 Key 填在这里
# 没收到前先留 None，代码也能跑，只是 Semantic Scholar 容易报错
S2_API_KEY = None
# ===========================================


class AcademicBaseTool:
    def __init__(self, proxy_base_url: str, api_key: str | None = None):
        self.proxy_base_url = proxy_base_url.rstrip("/")
        self.headers = {"User-Agent": "Academic-Project-Bot/1.0"}
        if api_key:
            self.headers["x-api-key"] = api_key


class SemanticScholarTool(AcademicBaseTool):
    async def search(self, query: str, limit: int = 3) -> list[dict]:
        endpoint = f"{self.proxy_base_url}/s2/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": limit,
            "fields": "title,abstract,year,authors,openAccessPdf,externalIds"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    endpoint,
                    params=params,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status == 429:
                        return [{"error": "请求太快被限制了 (等待 API Key 中...)"}]

                    resp.raise_for_status()
                    data = await resp.json()

            results = []
            for item in data.get("data", []):
                # 提取作者列表
                authors = item.get("authors", [])
                author_names = ", ".join([a.get("name", "") for a in authors[:5]])
                if len(authors) > 5:
                    author_names += " et al."

                # 优先使用 openAccessPdf，否则尝试从 externalIds 构造 arXiv 链接
                pdf_url = None
                if item.get("openAccessPdf"):
                    pdf_url = item["openAccessPdf"].get("url")
                elif item.get("externalIds", {}).get("ArXiv"):
                    arxiv_id = item["externalIds"]["ArXiv"]
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

                results.append({
                    "source": "Semantic Scholar",
                    "title": item.get("title"),
                    "authors": author_names,
                    "year": item.get("year"),
                    "abstract": item.get("abstract") or "无摘要",
                    "pdf_url": pdf_url
                })
            return results
        except Exception as e:
            return [{"error": f"S2 Error: {str(e)}"}]


class ArxivTool(AcademicBaseTool):
    async def search(self, query: str, max_results: int = 3) -> list[dict]:
        endpoint = f"{self.proxy_base_url}/arxiv/api/query"
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    endpoint,
                    params=params,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    resp.raise_for_status()
                    content = await resp.read()

            # xmltodict 是同步的，在线程池中运行
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, xmltodict.parse, content)

            entries = data.get("feed", {}).get("entry", [])
            if isinstance(entries, dict):
                entries = [entries]

            results = []
            for entry in entries:
                # 提取作者列表
                authors_data = entry.get("author", [])
                if isinstance(authors_data, dict):
                    authors_data = [authors_data]
                author_names = ", ".join([a.get("name", "") for a in authors_data[:5]])
                if len(authors_data) > 5:
                    author_names += " et al."

                results.append({
                    "source": "ArXiv",
                    "title": entry.get("title", "").replace("\n", "").strip(),
                    "authors": author_names,
                    "year": entry.get("published", "")[:4],  # 提取年份
                    "abstract": entry.get("summary", "").replace("\n", " "),
                    "pdf_url": entry.get("id", "").replace("abs", "pdf")
                })
            return results
        except Exception as e:
            return [{"error": f"ArXiv Error: {str(e)}"}]


# --- 测试运行 ---
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    def print_result(r: dict):
        """打印单条搜索结果"""
        if "error" in r:
            print(f"[X] {r.get('error')}")
            return
        print(f"[OK] 标题: {r.get('title')}")
        print(f"     作者: {r.get('authors')}")
        print(f"     年份: {r.get('year')}")
        print(f"     摘要: {r.get('abstract', '')[:100]}...")
        print(f"     PDF:  {r.get('pdf_url')}")
        print()

    async def main():
        # 1. 测试 ArXiv (应该 100% 成功)
        print("\n" + "=" * 60)
        print(">>> Testing ArXiv (No Key required)...")
        print("=" * 60)
        arxiv = ArxivTool(WORKER_URL)
        results = await arxiv.search("LLM Agents")
        for r in results:
            print_result(r)

        # 2. 测试 Semantic Scholar (没 Key 可能会 429，但也可能成功)
        print("\n" + "=" * 60)
        print(">>> Testing Semantic Scholar...")
        print("=" * 60)
        s2 = SemanticScholarTool(WORKER_URL, api_key=S2_API_KEY)
        results = await s2.search("LLM Agents")
        for r in results:
            print_result(r)

    asyncio.run(main())
