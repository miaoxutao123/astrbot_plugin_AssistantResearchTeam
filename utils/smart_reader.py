"""
智能阅读器 (Smart Reader) - 内容清洗工具 (异步版本)

功能：
1. HTML 转 Markdown：使用 Trafilatura 提取正文，丢弃无关元素
2. PDF 解析：自动检测 PDF 并提取文本
3. 元数据提取：返回发布时间、作者、引用列表等
"""

import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import aiohttp
import pymupdf
import trafilatura
from playwright.async_api import async_playwright
from trafilatura.metadata import extract_metadata


@dataclass
class ReadResult:
    """阅读结果数据类"""
    content: str  # Markdown 格式的正文
    title: str | None = None
    author: str | None = None
    publish_date: str | None = None
    url: str | None = None
    content_type: str = "html"  # html 或 pdf
    references: list[str] = field(default_factory=list)  # 引用列表
    error: str | None = None


async def _fetch_html_with_playwright(url: str) -> str:
    """使用 Playwright 异步获取渲染后的 HTML"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page = await context.new_page()

        # 隐藏 webdriver 特征
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_load_state("domcontentloaded")
        html_content = await page.content()
        await browser.close()

    return html_content


def _extract_references_from_text(text: str) -> list[str]:
    """从文本中提取引用/参考文献"""
    references = []

    # 匹配常见的引用格式
    # 1. [1] Author, Title, Year 格式
    bracket_refs = re.findall(r"\[(\d+)\]\s*([^\[\]]{10,200})", text)
    for num, ref in bracket_refs:
        references.append(f"[{num}] {ref.strip()}")

    # 2. DOI 链接
    dois = re.findall(r"(10\.\d{4,}/[^\s]+)", text)
    for doi in dois:
        if doi not in str(references):
            references.append(f"DOI: {doi}")

    # 3. arXiv 引用
    arxiv_refs = re.findall(r"(arXiv:\d{4}\.\d{4,5}(?:v\d+)?)", text, re.IGNORECASE)
    for ref in arxiv_refs:
        if ref not in str(references):
            references.append(ref)

    return references[:50]  # 限制最多 50 条引用


async def _read_html(url: str, use_playwright: bool = True) -> ReadResult:
    """异步读取 HTML 页面并提取内容"""
    try:
        if use_playwright:
            html_content = await _fetch_html_with_playwright(url)
        else:
            # 使用 aiohttp 进行简单请求，适用于静态页面
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response.raise_for_status()
                    html_content = await response.text()

        # 提取元数据 (trafilatura 是同步的，在线程池中运行)
        loop = asyncio.get_event_loop()
        metadata = await loop.run_in_executor(None, extract_metadata, html_content)

        # 提取正文并转为 Markdown
        text_content = await loop.run_in_executor(
            None,
            lambda: trafilatura.extract(
                html_content,
                include_comments=False,
                include_tables=True,
                include_links=True,
                output_format="markdown"
            )
        )

        if not text_content:
            return ReadResult(
                content="",
                url=url,
                error="无法从该网页提取到有效正文，可能是纯图片网页或受严密保护。"
            )

        # 提取引用
        references = _extract_references_from_text(text_content)

        return ReadResult(
            content=text_content,
            title=metadata.title if metadata else None,
            author=metadata.author if metadata else None,
            publish_date=metadata.date if metadata else None,
            url=url,
            content_type="html",
            references=references
        )

    except Exception as e:
        return ReadResult(content="", url=url, error=f"HTML 读取失败: {str(e)}")


async def _read_pdf(url: str) -> ReadResult:
    """异步读取 PDF 文件并提取内容"""
    try:
        # 异步下载 PDF
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                response.raise_for_status()
                pdf_bytes = await response.read()

        # PyMuPDF 是同步的，在线程池中运行
        loop = asyncio.get_event_loop()

        def parse_pdf(pdf_data: bytes) -> tuple:
            doc = pymupdf.open(stream=pdf_data, filetype="pdf")

            # 提取元数据
            metadata = doc.metadata
            title = metadata.get("title", "")
            author = metadata.get("author", "")
            creation_date = metadata.get("creationDate", "")

            # 解析创建日期
            publish_date = None
            if creation_date:
                match = re.match(r"D:(\d{4})(\d{2})(\d{2})", creation_date)
                if match:
                    publish_date = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

            # 提取所有页面的文本
            full_text = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                if text.strip():
                    full_text.append(f"## 第 {page_num + 1} 页\n\n{text}")

            doc.close()
            return title, author, publish_date, full_text

        title, author, publish_date, full_text = await loop.run_in_executor(
            None, parse_pdf, pdf_bytes
        )

        content = "\n\n".join(full_text)

        # 提取引用
        references = _extract_references_from_text(content)

        # 清理多余空行
        content = re.sub(r"\n{3,}", "\n\n", content)

        return ReadResult(
            content=content,
            title=title or None,
            author=author or None,
            publish_date=publish_date,
            url=url,
            content_type="pdf",
            references=references
        )

    except Exception as e:
        return ReadResult(content="", url=url, error=f"PDF 读取失败: {str(e)}")


def _is_pdf_url(url: str) -> bool:
    """判断 URL 是否指向 PDF 文件"""
    parsed = urlparse(url)
    path = parsed.path.lower()

    # 检查扩展名
    if path.endswith(".pdf"):
        return True

    # 检查常见的 PDF 服务路径
    pdf_patterns = [
        "/pdf/",
        "/download/pdf",
        "arxiv.org/pdf",
        "export=download",  # Google Drive
    ]
    return any(pattern in url.lower() for pattern in pdf_patterns)


async def smart_read(url: str, use_playwright: bool = True) -> ReadResult:
    """
    智能阅读器主函数 (异步)

    根据 URL 类型自动选择合适的解析方式：
    - PDF 文件：使用 PyMuPDF 解析
    - HTML 页面：使用 Playwright + Trafilatura 提取

    Args:
        url: 要读取的 URL
        use_playwright: 是否使用 Playwright 渲染 JS（默认 True）

    Returns:
        ReadResult: 包含正文、元数据和引用的结果对象
    """
    if _is_pdf_url(url):
        return await _read_pdf(url)
    else:
        return await _read_html(url, use_playwright)


async def smart_read_to_markdown(url: str, use_playwright: bool = True) -> str:
    """
    智能阅读并返回格式化的 Markdown 字符串 (异步)

    Args:
        url: 要读取的 URL
        use_playwright: 是否使用 Playwright 渲染 JS

    Returns:
        str: 格式化的 Markdown 内容，包含元数据
    """
    result = await smart_read(url, use_playwright)

    if result.error:
        return f"# 读取失败\n\n**错误**: {result.error}\n**URL**: {url}"

    # 构建 Markdown 输出
    output_parts = []

    # 标题
    if result.title:
        output_parts.append(f"# {result.title}")
    else:
        output_parts.append("# 未知标题")

    # 元数据块
    meta_parts = []
    if result.author:
        meta_parts.append(f"**作者**: {result.author}")
    if result.publish_date:
        meta_parts.append(f"**发布日期**: {result.publish_date}")
    meta_parts.append(f"**来源**: [{url}]({url})")
    meta_parts.append(f"**类型**: {result.content_type.upper()}")

    output_parts.append("\n".join(meta_parts))

    # 分隔线
    output_parts.append("---")

    # 正文
    output_parts.append(result.content)

    # 引用列表
    if result.references:
        output_parts.append("\n---\n## 参考文献\n")
        for ref in result.references:
            output_parts.append(f"- {ref}")

    return "\n\n".join(output_parts)


# --- 测试 ---
if __name__ == "__main__":
    async def main():
        # 测试 PDF
        test_url = "http://arxiv.org/pdf/2506.18783v1"
        print("=" * 50)
        print("测试 PDF 文件")
        print("=" * 50)
        result = await smart_read_to_markdown(test_url)
        print(result[:2000])  # 只打印前 2000 字符

    asyncio.run(main())
