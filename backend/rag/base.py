"""向量库抽象层。

上层（工具、Agent）只依赖这个接口，不关心底层是 Chroma、FAISS 还是 Milvus。
换实现时只改 backend/rag/__init__.py 里的一行，这也是面试时值得讲的设计点。

===================== 【课里没有】ABC 和 @abstractmethod =====================
你学过继承和多态，这个其实就是"继承 + 强制规矩"的加强版：

  普通父类：子类可以什么都不改，直接拿来用。
  抽象父类（ABC）：父类里标了 @abstractmethod 的方法**只是空壳**，
                   子类必须自己写一遍，否则实例化时直接报错。

为什么要这样：VectorStoreBase 规定了"任何向量库都得有 add_documents /
search / count / reset 四个方法"。Chroma 必须实现，将来换 Milvus 也必须实现。
哪天你少写一个，Python 立刻报错告诉你"这个类不完整"，而不是等到运行时
才发现"哦 my_store.count 不存在"。这叫"把错误提前到写代码的时候"。

ABC = Abstract Base Class（抽象基类），标准库里 abc 模块提供。
============================================================================
"""

from abc import ABC, abstractmethod
from typing import Iterable

from langchain_core.documents import Document


class VectorStoreBase(ABC):
    """所有向量库实现必须满足的契约。"""

    # @abstractmethod 只是"贴个标签"，说这个方法必须由子类实现，
    # 里面不写具体逻辑（只留一句文档说明）。
    @abstractmethod
    def add_documents(self, docs: Iterable[Document]) -> int:
        """写入文档，返回写入条数。"""

    @abstractmethod
    def search(
        self, query: str, k: int = 4, where: dict | None = None
    ) -> list[Document]:
        """按语义检索，返回最相近的 k 条文档片段。

        where 是元数据过滤条件（如 {"车型": "问界M9"}），
        用来把检索范围限制在某款车的资料里，避免跨车型串答案。
        """

    @abstractmethod
    def count(self) -> int:
        """库里现有片段数量。"""

    @abstractmethod
    def reset(self) -> None:
        """清空整个集合（重建库时用）。"""
