"""知识库检索工具（RAG）。

用法：把汽车 PDF / Markdown 放进 data/docs，跑一次
    python -m backend.rag.ingest --reset
建好 Chroma 库，这个工具就会被自动挂到 Agent 上。

检索策略：问题里点名了某款车，就只在那个车型的资料里找（元数据过滤），
没点名就全库检索——这样避免「问 M7 却拿 M9 的答案」。
"""

import re

from langchain_core.tools import tool

from ..rag import get_vector_store, store_ready

TOP_K = 4

MODEL_PATTERNS = [
    (re.compile(r"问界\s*M(\d+)", re.I), lambda m: f"问界M{m.group(1)}"),
    (re.compile(r"(?<![A-Za-z])M(\d+)(?!\d)", re.I), lambda m: f"问界M{m.group(1)}"),
    (re.compile(r"赛力斯\s*SF(\d+)", re.I), lambda m: f"赛力斯SF{m.group(1)}"),
    (re.compile(r"(?<![A-Za-z])SF(\d+)(?!\d)", re.I), lambda m: f"赛力斯SF{m.group(1)}"),
]


def detect_models(query: str) -> list[str]:
    """从问题里识别车型，返回去重后的车型标签。"""
    found: list[str] = []
    for pattern, fmt in MODEL_PATTERNS:
        for match in pattern.finditer(query):
            label = fmt(match)
            if label not in found:
                found.append(label)
    return found


@tool
def search_car_docs(query: str) -> str:
    """检索本地汽车知识库。适用于：车型参数配置、用户手册条款、保养周期、
    故障码含义、常见毛病处理等有明确文档依据的问题。query 传要查的具体问题，
    如果用户提到了车型（如 问界M7、M9、赛力斯SF5），请在 query 里带上车型名。"""
    if not store_ready():
        return "知识库尚未建立：请把资料放入 data/docs，运行 python -m backend.rag.ingest --reset"

    models = detect_models(query)
    where = {"车型": {"$in": models}} if models else None

    try:
        docs = get_vector_store().search(query, k=TOP_K, where=where)
        if not docs and where:
            # 指定车型没命中，退回全库，避免因为元数据没覆盖而空手而归
            docs = get_vector_store().search(query, k=TOP_K)
            where = None
    except Exception as exc:
        return f"知识库检索出错：{type(exc).__name__}: {exc}"

    if not docs:
        return f"知识库中没有检索到与「{query}」相关的内容。"

    scope = f"（限定车型：{'、'.join(models)}）" if where else "（全库）"
    lines = [f"知识库检索：{query} {scope}", ""]
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "未知来源")
        page = doc.metadata.get("page")
        model = doc.metadata.get("车型", "")
        loc = f"{source}"
        if page is not None:
            loc += f" 第{page + 1}页"
        if model:
            loc += f"（{model}）"
        lines.append(f"[{i}] 来源：{loc}")
        lines.append(doc.page_content.strip())
        lines.append("")
    return "\n".join(lines)
