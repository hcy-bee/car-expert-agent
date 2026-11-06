"""RAG 模块统一出口。

上层只 import 这里的 get_vector_store / store_ready，
换底层实现（Chroma -> FAISS / Milvus）只需要改本文件。
"""

from ..config import settings
from .base import VectorStoreBase

_store: VectorStoreBase | None = None


def store_ready() -> bool:
    """建库脚本是否已经跑过（不打开数据库，避免 Windows 文件锁）。"""
    return (settings.chroma_dir / "chroma.sqlite3").exists()


def get_vector_store() -> VectorStoreBase:
    """懒加载单例。"""
    global _store
    if _store is None:
        from .chroma_store import ChromaStore

        _store = ChromaStore()
    return _store


__all__ = ["VectorStoreBase", "get_vector_store", "store_ready"]
