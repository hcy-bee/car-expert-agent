# 汽车文档放这里

阶段 4 建知识库时，把资料丢进这个目录即可，支持：

- `.pdf`（车型手册、参数配置表、保养规范）
- `.md` / `.txt`（自己整理的 FAQ、故障码对照表、选车笔记）

## 当前语料（3 份官方使用说明书，共 868 页 / 约 61 万字）

| 文件 | 页码 | 车型 | 来源 |
|---|---|---|---|
| `问界M7_使用说明书.pdf` | 227 | 问界M7 | [aito.auto 服务支持](https://aito.auto/service/) |
| `问界M9_2025款增程版_使用说明书.pdf` | 440 | 问界M9 | 同上 |
| `赛力斯SF5_使用说明书.pdf` | 201 | 赛力斯SF5 | [owoss.seres.cn](https://owoss.seres.cn/pdf/) |

三份都是**官方 PDF、带文字层**（不是扫描件），`pypdf` 可直接提取。

## 为什么这些 PDF 不进 git

单份 15~69 MB，三份合计 128 MB，既超 GitHub 建议体积，也涉及厂商版权（手册首页写明「版权归赛力斯汽车有限公司所有」）。

所以 `.gitignore` 排除了 `data/docs/*.pdf`，仓库里只保留**下载脚本**：

```bash
python fetch_docs.py          # 在 car_agent 目录下运行
```

脚本从官方地址重新下载，clone 下来的人跑一次就有同样的语料。

## 换/加资料后必须重建索引

```bash
# 先停掉后端，否则 Windows 上 Chroma 会 database is locked
python -m backend.rag.ingest --reset
```

文件名决定 `车型` 元数据（`问界M7` / `问界M9` / `赛力斯SF5`），检索时会按车型过滤。
新加车型请让文件名里带上 `问界M*` 或 `赛力斯SF*`，否则会标成「通用」，拿不到过滤收益。
