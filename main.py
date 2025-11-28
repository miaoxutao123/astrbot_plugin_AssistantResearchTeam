from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.api.star import Context, Star, register
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext


@register("deepresearch", "miaomiao", "基于Gemini的简单deepresearch实现", "0.0.1")
class MyPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.search_contexts: dict[str, list[dict]] = {}
        self.search_provider_id = config.get("search_provider_id", "gemini_with_search")

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        # 打印所有可用的 Provider ID（调试用）
        print("=== Available Providers ===")
        for prov in self.context.get_all_providers():
            print(f"  ID: {prov.meta().id}, Type: {type(prov).__name__}")
        print("===========================")

        # 注册 gemini_search 工具
        self.context.add_llm_tools(GeminiSearchTool())


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
