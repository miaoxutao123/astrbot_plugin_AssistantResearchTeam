import os

from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.api.star import Context, Star, register
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.core.message.components import File
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.agent.tool import ToolSet

from .utils.document_utils import DocumentManager, MarkdownToWordConverter
from .utils.scholar import ArxivTool, CNKITool
from .utils.smart_reader import smart_read_to_markdown


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
        # print("=== Available Providers ===")
        # for prov in self.context.get_all_providers():
        #     print(f"  ID: {prov.meta().id}, Type: {type(prov).__name__}")
        # print("===========================")

        # 注册工具
        arxiv_tool = ArxivSearchTool()
        arxiv_tool.proxy_base_url = self.scholar_proxy_base_url or ""
        self.context.add_llm_tools(
            GeminiSearchTool(),
            arxiv_tool,
            CNKISearchTool(),
            SmartReader(),
            DocumentProcessor(),
            SendFileTool(),
            DocumentReviewer()
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
        keyword = kwargs.get("keywords", "")
        if not keyword:
            return "Keywords are required."
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
class CNKISearchTool(FunctionTool[AstrAgentContext]):
    name: str = "cnki_search"
    description: str = "Use CNKITool to search for Chinese academic papers on CNKI (知网) based on keywords."
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "string",
                    "description": "Keywords to search for academic papers on CNKI (知网).",
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

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        keyword = kwargs.get("keywords", "")
        if not keyword:
            return "Keywords are required."
        max_results = kwargs.get("max_results", 3)
        print(f"[CNKISearchTool] Searching for: {keyword}, max_results: {max_results}")
        cnki_tool = CNKITool(headless=True)
        results = await cnki_tool.search(query=keyword, max_results=max_results)
        print(f"[CNKISearchTool] Results: {results}")

        if not results:
            return "No results found."

        if results and "error" in results[0]:
            return f"Search error: {results[0]['error']}"

        response_lines = []
        for idx, paper in enumerate(results, start=1):
            response_lines.append(f"{idx}. Title: {paper.get('title', 'N/A')}\n   Authors: {paper.get('authors', 'N/A')}\n   Year: {paper.get('year', 'N/A')}\n   Abstract: {paper.get('abstract', 'N/A')}\n   URL: {paper.get('pdf_url', 'N/A')}\n")

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
        url = kwargs.get("url", "")
        if not url:
            return "URL is required."
        markdown_content = await smart_read_to_markdown(url)
        return markdown_content

@dataclass
class DocumentProcessor(FunctionTool[AstrAgentContext]):
    name: str = "Document_Processor"
    description: str = "A tool to create, read, write, delete, and list markdown or docx documents. Supports operations: create, read, write(append), write(cover), delete, list."
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
        dm = DocumentManager(base_dir="./data/plugin_data/astrbot_plugin_AssistantResearchTeam")
        mtw = MarkdownToWordConverter()

        document_type = kwargs.get("document_type", "")
        document_name = kwargs.get("document_name", "")
        process_type = kwargs.get("process_type", "")
        document_content = kwargs.get("document_content", "")

        if not document_name:
            return "Document name is required."

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

@dataclass
class SendFileTool(FunctionTool[AstrAgentContext]):
    name: str = "send_file"
    description: str = "A tool to send files to the user. Use this when you need to send a generated file (like .docx, .pdf, .md) to the user."
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path of the file to send.",
                },
            },
            "required": ["file_path"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        file_path = kwargs.get("file_path")

        if not file_path or not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"

        # Get Context and Event
        astr_context = context.context.context
        event = context.context.event
        umo = event.unified_msg_origin

        # Construct MessageChain
        chain = MessageChain()
        chain.chain.append(File(name=os.path.basename(file_path), file=file_path))

        # Send message
        await astr_context.send_message(umo, chain)

        return f"File {os.path.basename(file_path)} has been sent to the user."

@dataclass
class DocumentReviewer(FunctionTool[AstrAgentContext]):
    name: str = "document_reviewer"
    description: str = "A subaent Used to review whether the answers or research in the document are comprehensive and whether any additions are needed."
    parameters:dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "document_name": {
                    "type": "string",
                    "description": "The name of the document to review.",
                },
                "question": {
                    "type": "string",
                    "description": "The question that the document answers or research is related to.",
                },
            },
            "required": ["document_name", "question"],
        }
    )
    async def call(
            self, context: ContextWrapper[AstrAgentContext], **kwargs
            ) -> ToolExecResult:
        review_provider_id: str = "review_agent"
        prompt = "Please use DocumentProceser yourself to extract the document content from the given document name. \
                Evaluate whether the answer or research in the document is comprehensive and whether it requires additional content. \
                If supplementation is needed, please provide specific suggestions for what to add. \
                When necessary (e.g., if you find the information ambiguous, or if the relevant knowledge is not available in your knowledge base), \
                use the gemini_search tool to search for information on this topic and incorporate the search results into your supplementary suggestions."
        astr_context = context.context.context
        llm_resp = await astr_context.tool_loop_agent(
            contexts=[],
            chat_provider_id = review_provider_id,   # LLM provider ID
            system_prompt = (prompt),
            prompt = f"Question: {kwargs['question']}\nDocument_name: {kwargs['document_name']}",
            tools = ToolSet([GeminiSearchTool(), DocumentProcessor()]),
            max_steps = 10,
            event=context.context.event
        )
        return llm_resp.completion_text

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
