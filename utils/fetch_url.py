##################################################################
# 此工具已过时，请使用 smart_reader
# 保留此文件仅为向后兼容，内部调用 smart_reader
##################################################################

import asyncio

from .smart_reader import smart_read


async def fetch_url_content_local(url: str) -> str:
    """
    本地实现的网页抓取工具 (异步版本)。
    使用无头浏览器加载网页，并提取正文转换为Markdown。

    已过时：请直接使用 smart_reader.smart_read() 或 smart_reader.smart_read_to_markdown()
    """
    result = await smart_read(url, use_playwright=True)

    if result.error:
        return f"Error fetching URL: {result.error}"

    return result.content or "Error: 无法从该网页提取到有效正文，可能是纯图片网页或受严密保护。"


# --- 测试一下 ---
if __name__ == "__main__":
    async def main():
        # 测试抓取一篇百度百科页面
        url = "https://baike.baidu.com/item/%E6%9D%8F%E8%8A%B1%E6%9D%91%E9%A3%8E%E6%99%AF%E5%8C%BA/9824443?fr=aladdin"
        result = await fetch_url_content_local(url)
        print(result[:2000])

    asyncio.run(main())
