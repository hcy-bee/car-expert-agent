"""下载示例汽车手册到 data/docs（仓库里不存 PDF，用这个脚本复现）。

用法（在 car_agent 目录下）：

    python fetch_docs.py            # 缺哪份下哪份
    python fetch_docs.py --force    # 全部重下

三份都是厂商官网公开的使用说明书，带文字层，pypdf 可直接提取。
"""

import argparse
import sys
from pathlib import Path

import requests

DOCS_DIR = Path(__file__).resolve().parent / "data" / "docs"

DOCS = [
    {
        "filename": "问界M7_使用说明书.pdf",
        "pages": 227,
        "size": "15 MB",
        "url": "https://seres-www-prod.oss-cn-shanghai.aliyuncs.com/pdf/"
        "AITO+M7%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E%E4%B9%A6.pdf",
    },
    {
        "filename": "问界M9_2025款增程版_使用说明书.pdf",
        "pages": 440,
        "size": "46 MB",
        "url": "https://aito.auto/dam/content/dam/aito/cn/service/pdf/261015/"
        "%E9%97%AE%E7%95%8CM92025%E6%AC%BE%E5%A2%9E%E7%A8%8B%E7%89%88"
        "%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E%E4%B9%A6.pdf",
    },
    {
        "filename": "赛力斯SF5_使用说明书.pdf",
        "pages": 201,
        "size": "69 MB",
        "url": "https://owoss.seres.cn/pdf/"
        "%E8%B5%9B%E5%8A%9B%E6%96%AFSF5%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E%E4%B9%A6.pdf",
    },
]


def download(doc: dict, force: bool = False) -> None:
    target = DOCS_DIR / doc["filename"]
    if target.exists() and not force:
        print(f"[跳过] {doc['filename']} 已存在（{target.stat().st_size / 1e6:.1f} MB）")
        return

    print(f"[下载] {doc['filename']}（约 {doc['size']}，{doc['pages']} 页）")
    tmp = target.with_suffix(".part")
    with requests.get(doc["url"], stream=True, timeout=(10, 300)) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r       {done / total * 100:5.1f}%", end="", flush=True)
    print()

    if tmp.stat().st_size < 1_000_000:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("文件太小，可能不是有效 PDF（地址失效了？）")
    tmp.replace(target)
    print(f"[完成] {doc['filename']} -> {target.stat().st_size / 1e6:.1f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description="下载示例汽车手册")
    parser.add_argument("--force", action="store_true", help="已存在也重新下载")
    args = parser.parse_args()

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for doc in DOCS:
        try:
            download(doc, force=args.force)
        except Exception as exc:
            print(f"[失败] {doc['filename']}：{type(exc).__name__}: {exc}")
            print("       可以手动打开 https://aito.auto/service/ 下载后改名放进来")
            sys.exit(1)

    print("\n下一步：python -m backend.rag.ingest --reset（记得先停掉后端）")


if __name__ == "__main__":
    main()
