# AstrBot Plugin DeepResearch

基于 Gemini 的简单 DeepResearch 实现，为 AstrBot 添加联网深度搜索能力。

## 简介

本插件为 AstrBot 注册了一个名为 `gemini_search` 的工具。该工具利用 Gemini 的搜索能力（Grounding with Google Search）来执行网络搜索，并生成详细的查询结果，从而让你的 Bot 能够回答需要实时信息的问题。

## 功能

- **联网搜索**: 允许 LLM 通过调用工具进行实时网络搜索。
- **深度整合**: 利用 Gemini 的能力对搜索结果进行分析、总结和引用。

## 安装与配置

### 1. 前置要求

- 拥有 Google Gemini API Key，并确保该 Key 有权限使用 Search Grounding 功能。
- 在 AstrBot 中配置了 Gemini 对应的 LLM 提供商。

### 2. 插件配置

本插件需要指定一个用于执行搜索的 LLM 提供商 ID。

默认情况下，插件会寻找 ID 为 `gemini_with_search` 的提供商。如果你的配置不同，请在插件配置中进行修改。

**配置项：**

- `search_provider_id`: (可选) 用于执行搜索的 LLM 提供商 ID。默认为 `gemini_with_search`。

**配置示例：**

如果你的 Gemini 提供商 ID 是 `gemini_pro`，则配置如下：

```json
{
  "search_provider_id": "gemini_pro"
}
```

## 使用方法

1. 加载并启用本插件。
2. 在与 AstrBot 对话时，提出需要联网搜索的问题。
   - 例如：“帮我搜索一下最近关于 DeepSeek 的新闻”
   - 例如：“查找一下 Python 3.13 的新特性”
3. LLM 会自动判断并调用 `gemini_search` 工具，返回基于搜索结果的回答。

## 开发者信息

- **作者**: miaomiao
- **版本**: 0.0.1
