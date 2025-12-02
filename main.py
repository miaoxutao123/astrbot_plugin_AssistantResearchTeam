from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.api.star import Context, Star, register
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext

from .utils.scholar import ArxivTool
from .utils.smart_reader import smart_read_to_markdown
from .utils.document_utils import DocumentManager,MarkdownToWordConverter

@register("deepresearch", "miaomiao", "基于Gemini的简单deepresearch实现", "0.0.1")
class MyPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.search_contexts: dict[str, list[dict]] = {}
        self.search_provider_id = config.get("search_provider_id", "gemini_with_search")
        self.scholar_proxy_base_url = config.get("scholar_proxy_base_url")

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        # 打印所有可用的 Provider ID（调试用）
        print("=== Available Providers ===")
        for prov in self.context.get_all_providers():
            print(f"  ID: {prov.meta().id}, Type: {type(prov).__name__}")
        print("===========================")

        # 注册工具
        self.context.add_llm_tools(
            GeminiSearchTool(),
            ArxivSearchTool(proxy_base_url=self.scholar_proxy_base_url or ""),
            SmartReader(),
            DocumentProceser()
        )


    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""

@dataclass
class GeminiSearchTool(FunctionTool[AstrAgentContext]):
    name: str = "gemini_search"
    description: str = "Use Gemini's search capabilities to perform web searches and generate detailed search results for the query."
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "string",
                    "description": "Keywords or questions to search on the web.",
                },
            },
            "required": ["keywords"],
        }
    )
    search_provider_id: str = "gemini_with_search"

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        keyword = kwargs.get("keywords")
        system_prompt = "You are a web search expert leveraging Gemini and Google Search, able to perform searches based on keywords or questions provided by the user and return detailed results while clearly citing their sources."

        # 通过 context.context.context 获取 Star 的 Context
        astrbot_context: Context = context.context.context

        llm_resp = await astrbot_context.llm_generate(
            chat_provider_id=self.search_provider_id,
            prompt=keyword,
            system_prompt=system_prompt,
            contexts=[],
        )
        return llm_resp.completion_text

@dataclass
class ArxivSearchTool(FunctionTool[AstrAgentContext]):
    name: str = "arxiv_search"
    description: str = "Use ArxivTool to search for academic papers on arXiv based on keywords."
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "string",
                    "description": "Keywords to search for academic papers on arXiv.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return.",
                    "default": 3,
                }
            },
            "required": ["keywords", "max_results"],
        }
    )
    proxy_base_url: str = ""

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        keyword = kwargs.get("keywords")
        max_results = kwargs.get("max_results", 3)
        print(f"[ArxivSearchTool] Searching for: {keyword}, max_results: {max_results}, proxy_base_url: {self.proxy_base_url}")
        arxiv_tool = ArxivTool(proxy_base_url=self.proxy_base_url)
        results = await arxiv_tool.search(query=keyword, max_results=max_results)
        print(f"[ArxivSearchTool] Results: {results}")

        if not results:
            return "No results found."

        # 检查是否返回了错误
        if results and "error" in results[0]:
            return f"Search error: {results[0]['error']}"

        response_lines = []
        for idx, paper in enumerate(results, start=1):
            response_lines.append(f"{idx}. Title: {paper.get('title', 'N/A')}\n   Authors: {paper.get('authors', 'N/A')}\n   Year: {paper.get('year', 'N/A')}\n   Abstract: {paper.get('abstract', 'N/A')}\n   PDF URL: {paper.get('pdf_url', 'N/A')}\n")

        return "\n".join(response_lines)

@dataclass
class SmartReader(FunctionTool[AstrAgentContext]):
    name: str = "smart_reader"
    description: str = "A tool to intelligently read and extract content from web pages or PDF documents given their URLs. It can handle dynamic web pages using a headless browser and extract text in Markdown format."
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL of the web page or PDF document to read.",
                },
            },
            "required": ["url"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        url = kwargs.get("url")
        markdown_content = await smart_read_to_markdown(url)
        return markdown_content

@dataclass
class DocumentProceser(FunctionTool[AstrAgentContext]):
    name: str = "Document_Proceser"
    description: str = ""
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "document_type": {
                    "type": "string",
                    "description": "The type of the document to process.(markdown/docx)",
                },
                "document_content": {
                    "type": "string",
                    "description": "The content of the document to process. If creating a docx file, content should be in markdown format.",
                },
                "document_name": {
                    "type": "string",
                    "description": "The name of the document to process.",
                },
                "process_type": {
                    "type": "string",
                    "description": "The type of processing to perform on the document.(create/read/write(append)/write(cover)/delete/list)",
                }
            },
            "required": ["document_type", "document_name", "process_type"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        dm = DocumentManager(base_dir="./documents")
        mtw = MarkdownToWordConverter()

        document_type = kwargs.get("document_type")
        document_name = kwargs.get("document_name")
        process_type = kwargs.get("process_type")
        document_content = kwargs.get("document_content", "")

        match process_type:
            case "create":
                if document_type == "markdown":
                    filepath = dm.create(document_name, document_content)
                    return f"Markdown 文件已创建: {filepath}"
                elif document_type == "docx":
                    filepath = mtw.convert(document_content, document_name)
                    return f"Word 文件已创建: {filepath}"
                else:
                    return "不支持的文档类型。"
            case "read":
                content = dm.read(document_name)
                return content
            case "write(append)":
                dm.write(document_name, document_content, append= True)
                return f"文件已追加内容: {document_name}"
            case "write(cover)":
                dm.write(document_name, document_content, append= False)
                return f"文件已覆盖内容: {document_name}"
            case "delete":
                dm.delete(document_name)
                return f"文件已删除: {document_name}"
            case "list":
                files = dm.list_files()
                return "md文件列表:\n" + "\n".join(files)
            case _:
                return "不支持的处理方法类型。"

# @dataclass
# class BilibiliTool(FunctionTool[AstrAgentContext]):
#     name: str = "bilibili_videos"  # 工具名称
#     description: str = "A tool to fetch Bilibili videos."  # 工具描述
#     parameters: dict = Field(
#         default_factory=lambda: {
#             "type": "object",
#             "properties": {
#                 "keywords": { # 参数名
#                     "type": "string",# 参数类型
#                     "description": "Keywords to search for Bilibili videos.",# 参数说明
#                 },
#             },
#             "required": ["keywords"], # 必填参数
#         }
#     )

#     async def call(
#         self, context: ContextWrapper[AstrAgentContext], **kwargs
#     ) -> ToolExecResult:
#         return "1. 视频标题：如何使用AstrBot\n视频链接：xxxxxx"
