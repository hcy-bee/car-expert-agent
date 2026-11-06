"""联网搜索工具：让 Agent 能查实时信息（新车、价格、评测、政策）。"""

from langchain_core.tools import tool

from ..config import settings


@tool
def web_search(query: str) -> str:
    """联网搜索实时汽车信息。适用于：新车上市、当前价格/优惠、最新评测、
    召回与政策法规等有时效性的问题。query 传具体的中文关键词，例如
    "2026 年 20 万级纯电 SUV 推荐" 或 "某车型 最新优惠"。"""
    if not settings.tavily_api_key:
        return "联网搜索未启用：请在 .env 中配置 TAVILY_API_KEY。"

    from tavily import TavilyClient

    client = TavilyClient(api_key=settings.tavily_api_key)
    resp = client.search(query=query, max_results=5, search_depth="basic")

    results = resp.get("results", [])
    if not results:
        return f"没有搜到与「{query}」相关的结果。"

    lines = [f"搜索关键词：{query}", ""]
    for i, item in enumerate(results, 1):
        title = item.get("title", "无标题")
        url = item.get("url", "")
        content = (item.get("content") or "").strip().replace("\n", " ")
        if len(content) > 400:
            content = content[:400] + "…"
        lines.append(f"[{i}] {title}")
        lines.append(f"    链接：{url}")
        lines.append(f"    摘要：{content}")
        lines.append("")
    return "\n".join(lines)
