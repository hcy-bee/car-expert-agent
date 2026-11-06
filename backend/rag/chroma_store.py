"""Chroma 实现：数据落在 data/chroma 目录，进程重启不丢。

三个关键概念：
- collection        相当于一张表，换名字就是换一个独立数据集
- persist_directory 数据存哪个目录
- embedding_function 用哪个向量化模型（换模型必须清库重建）
"""

from typing import Iterable

from langchain_core.documents import Document

from ..config import settings
from .base import VectorStoreBase


class ChromaStore(VectorStoreBase):
    def __init__(
        self,
        collection_name: str = "car_docs",
        persist_directory: str | None = None,
    ) -> None:
        from langchain_chroma import Chroma

        from .embedding import get_embeddings

        self.persist_directory = persist_directory or str(settings.chroma_dir)
        self.collection_name = collection_name
        self._store = Chroma(
            collection_name=collection_name,
            embedding_function=get_embeddings(),
            persist_directory=self.persist_directory,
        )

    def add_documents(self, docs: Iterable[Document]) -> int:
        docs = list(docs)
        if not docs:
            return 0
        self._store.add_documents(docs)
        return len(docs)

    def search(
        self, query: str, k: int = 4, where: dict | None = None
    ) -> list[Document]:
        # langchain-chroma 里元数据过滤参数叫 filter（底层就是 Chroma 的 where）
        if where:
            return self._store.similarity_search(query, k=k, filter=where)
        return self._store.similarity_search(query, k=k)

    def count(self) -> int:
        return self._store._collection.count()

    def reset(self) -> None:
        self._store.reset_collection()
