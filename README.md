# AstrBot Plugin AssistantResearchTeam

为 AstrBot 提供 AI 研究助手能力的插件，集成联网搜索、学术论文检索、智能阅读和文档处理等功能。

## 功能特性

**联网搜索** - 利用 Gemini 的 Google Search Grounding 能力进行实时网络搜索，返回带引用来源的详细结果。

**学术论文检索** - 支持 ArXiv 和知网 (CNKI) 论文搜索，可自定义返回结果数量，获取论文标题、作者、摘要及链接。

**智能阅读器** - 自动识别 URL 类型（网页/PDF），使用 Playwright 渲染动态页面，提取正文内容并转换为 Markdown 格式，同时提取元数据和参考文献。

**文档处理** - 支持 Markdown 和 Word 文档的创建、读取、写入、删除操作，可将 Markdown 内容转换为格式化的 Word 文档。

**文件发送** - 将生成的文档（.docx、.pdf、.md 等）直接发送给用户。

## 安装与配置

### 前置要求

- AstrBot 环境
- Google Gemini API Key（需支持 Search Grounding 功能）
- 已配置 Gemini LLM 提供商

### 依赖安装

```bash
pip install aiohttp xmltodict python-docx pymupdf trafilatura playwright DrissionPage
playwright install chromium
```

> 注：知网搜索功能**首次调用时**会自动下载 Chromium 浏览器到 `utils/browsers/` 目录（约 200MB），请确保网络畅通。

**手动下载 Chromium（可选）：**
```bash
python utils/cnki/browser.py
```

### 插件配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `search_provider_id` | 用于执行搜索的 LLM 提供商 ID | `gemini_with_search` |
| `scholar_proxy_base_url` | ArXiv 搜索代理地址（可选） | 空 |

配置示例：

```json
{
  "search_provider_id": "gemini_pro",
  "scholar_proxy_base_url": "https://your-proxy.workers.dev"
}
```

## 注册的工具

本插件为 AstrBot 注册以下 LLM 工具：

| 工具名称 | 功能描述 |
|----------|----------|
| `gemini_search` | 使用 Gemini 进行联网搜索 |
| `arxiv_search` | 搜索 ArXiv 学术论文 |
| `cnki_search` | 搜索知网 (CNKI) 中文学术论文 |
| `smart_reader` | 智能读取网页或 PDF 内容 |
| `Document_Processor` | 文档创建、读取、写入、删除 |
| `send_file` | 向用户发送文件 |
| `document_reviewer` | 文档审核子代理 |

## 使用示例

与 Bot 对话时，LLM 会根据需求自动调用相应工具：

- "帮我搜索最近关于大语言模型的新闻" → 调用 `gemini_search`
- "查找 ArXiv 上关于 LLM Agent 的论文" → 调用 `arxiv_search`
- "搜索知网上关于深度学习的论文" → 调用 `cnki_search`
- "阅读这篇论文的内容：https://arxiv.org/pdf/xxx" → 调用 `smart_reader`
- "把研究结果整理成 Word 文档" → 调用 `Document_Processor`
- "把文档发给我" → 调用 `send_file`

## 开发者信息

- **作者**: miaomiao
- **版本**: 0.0.1
