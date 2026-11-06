"""建立 / 重建汽车知识库（Chroma）。

用法（在 car_agent 目录下）：

    # 首次建库
    python -m backend.rag.ingest

    # 清空重建（改了资料或者换了 embedding 模型时必须加 --reset）
    python -m backend.rag.ingest --reset

    # 只索引某个子目录
    python -m backend.rag.ingest --path data/docs/比亚迪 --reset

注意：运行时先把后端停掉，否则 Windows 上 Chroma 的 SQLite 会报 database is locked。
"""

import argparse
import re
import sys
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..config import settings

SUPPORTED = {".pdf", ".md", ".markdown", ".txt"}
SKIP_NAMES = {"README.md", "readme.md", "README.txt"}
BATCH_SIZE = 64

# 从文件名识别车型，写进元数据，检索时可以按车型过滤（避免问 M7 结果答成 M9）
MODEL_PATTERNS = [
    (re.compile(r"问界\s*M(\d+)", re.I), lambda m: f"问界M{m.group(1)}"),
    (re.compile(r"赛力斯\s*SF(\d+)", re.I), lambda m: f"赛力斯SF{m.group(1)}"),
]

# 封面/前言/版权页这类套话页，几乎每份手册都有，检索时是纯噪音
BOILERPLATE = ("感谢您选择", "版权归赛力斯汽车有限公司所有", "本手册版权归")


def detect_model(filename: str) -> str:
    for pattern, fmt in MODEL_PATTERNS:
        found = pattern.search(filename)
        if found:
            return fmt(found)
    return "通用"


def _is_noise(text: str, page: int | None) -> bool:
    """过滤封面/前言/版权页，以及提取不出文字的图片页。"""
    stripped = text.strip()
    if len(stripped) < 40:
        return True
    if page is not None and page < 4 and any(k in stripped for k in BOILERPLATE):
        return True
    return False


def load_file(path: Path, root: Path) -> list[Document]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from langchain_community.document_loaders import PyPDFLoader

        docs = PyPDFLoader(str(path)).load()
    elif suffix in {".md", ".markdown"}:
        # Markdown 先按标题切，保证「一节 = 一个语义块」，表格不会被拦腰截断
        from langchain_text_splitters import MarkdownHeaderTextSplitter

        text = path.read_text(encoding="utf-8")
        docs = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "h1"), ("##", "h2")],
            strip_headers=False,
        ).split_text(text)
    elif suffix == ".txt":
        from langchain_community.document_loaders import TextLoader

        docs = TextLoader(str(path), encoding="utf-8").load()
    else:
        return []

    model = detect_model(path.stem)
    if path.suffix.lower() == ".pdf":
        # 只看 PDF 的逐页结果；Markdown 的段落太短是正常的，不能按长度过滤
        kept = [d for d in docs if not _is_noise(d.page_content, d.metadata.get("page"))]
        if len(kept) < len(docs):
            print(f"        （过滤掉 {len(docs) - len(kept)} 页封面/前言/空页）")
        docs = kept

    for doc in docs:
        doc.metadata["source"] = str(path.relative_to(root))
        doc.metadata["车型"] = model
    return docs


def collect_documents(root: Path) -> tuple[list[Document], list[Path]]:
    docs: list[Document] = []
    used: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        if path.name in SKIP_NAMES:
            continue
        try:
            loaded = load_file(path, root)
        except Exception as exc:
            print(f"  [跳过] {path.name}：{type(exc).__name__}: {exc}")
            continue
        if loaded:
            docs.extend(loaded)
            used.append(path)
            print(f"  [读取] {path.relative_to(root)}  ({len(loaded)} 段/页)")
    return docs, used


def main() -> None:
    parser = argparse.ArgumentParser(description="建立汽车知识库")
    parser.add_argument("--reset", action="store_true", help="清空已有集合后重建")
    parser.add_argument("--path", default=str(settings.docs_dir), help="资料目录")
    parser.add_argument("--chunk-size", type=int, default=400)
    parser.add_argument("--chunk-overlap", type=int, default=60)
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"目录不存在：{root}")
        sys.exit(1)

    print(f"资料目录：{root}")
    print("正在读取文档…")
    raw_docs, used = collect_documents(root)
    if not raw_docs:
        print("\n没有找到可用资料。支持 .pdf / .md / .txt，请先放入 data/docs。")
        sys.exit(1)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
    )
    chunks = splitter.split_documents(raw_docs)
    print(f"\n共 {len(used)} 个文件，切成 {len(chunks)} 个片段")

    from . import get_vector_store, store_ready

    store = get_vector_store()
    if args.reset:
        print("清空旧集合并重建…" if store_ready() else "首次建库…")
        store.reset()

    added = 0
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        added += store.add_documents(batch)
        print(f"  已写入 {added}/{len(chunks)}")

    print(f"\n完成：向量库现在共有 {store.count()} 个片段")
    print(f"数据目录：{settings.chroma_dir}")
    print("重启后端后，/health 的 tools 里会出现 search_car_docs")


if __name__ == "__main__":
    main()
