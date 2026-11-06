# 汽车专家 Agent

从「Streamlit 直连大模型」升级为「FastAPI 后端 + LangChain Agent + 工具」的完整项目。
阶段 1~5 均已跑通：后端化、Agent 化、联网搜索、Chroma 知识库、多轮记忆（LangGraph SqliteSaver）。

> 看不懂代码？先读 **[手册-如何读懂这个项目.md](./手册-如何读懂这个项目.md)**：
> 按「Python 基础 + 面向对象 + FastAPI 五个文件 + LangChain 2.1–2.6 + RAG 七个 notebook」
> 这个知识边界写的，逐文件讲解 + 5 个新知识点从零讲透。

## 一、结构

```
PythonProject/
├── 第二章langchain/      课程代码
├── 第四章RAG/            课程代码
└── car_agent/           ← 本项目，挂在 PythonProject 这个 PyCharm 项目里
    ├── backend/
    │   ├── config.py        所有配置和路径（读 .env）
    │   ├── prompts.py       汽车专家系统提示词（改人设只改这里）
    │   ├── llm.py           模型接入：LangChain / 原生 SDK 两条路
    │   ├── agent_core.py    Agent 组装 + 流式事件（核心文件）
    │   ├── main.py          FastAPI 接口：/health、/chat(SSE)、/chat/sync
    │   ├── tools/
    │   │   ├── web_search.py   联网搜索（Tavily）
    │   │   └── rag_search.py   知识库检索工具（只依赖抽象接口）
    │   └── rag/
    │       ├── base.py         向量库抽象接口（换实现只改这里）
    │       ├── chroma_store.py Chroma 实现（默认）
    │       ├── embedding.py    向量化模型（百炼 / 方舟）
    │       └── ingest.py       建库脚本：加载 → 切分 → 入库
    ├── frontend/app.py      Streamlit 界面，只调后端
    ├── data/
    │   ├── docs/            汽车 PDF / Markdown（PDF 不入库，见 fetch_docs.py）
    │   ├── chroma/          向量库数据（自动生成，已 gitignore）
    │   ├── agent_memory.db  LangGraph 记忆库（自动生成，已 gitignore）
    │   └── sessions/        会话 JSON（已 gitignore）
    ├── fetch_docs.py        下载 3 份官方使用说明书（复现语料）
    ├── .gitignore
    └── check_env.py         环境体检脚本
```

## 二、怎么启动

**顺序永远是：先后端（8000），再前端（8501）。** 前端启动时会去问后端 `/health`，后端没起就会显示「未连接」。

**方式 A：在 PyCharm 里点绿三角（推荐）**

右上角运行配置下拉里已经有两个配置（若没看到，`File → Reload from Disk` 或重启 PyCharm）：

- `car_agent 后端 (8000)` → 先跑这个
- `car_agent 前端 (8501)` → 再跑这个

两个配置都已指定解释器 `PythonProject\.venv`、工作目录 `car_agent`、环境文件 `car_agent\.env`，不用手填任何东西。

**方式 B：双击 bat**

1. 双击 `run_backend.bat` → 浏览器打开 http://127.0.0.1:8000/docs 能看到接口列表
2. 双击 `run_frontend.bat` → 浏览器打开 http://127.0.0.1:8501 开始聊天

**方式 C：命令行**

```bat
cd /d E:\python-project\PythonProject\car_agent
E:\python-project\PythonProject\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
:: 另开一个窗口
E:\python-project\PythonProject\.venv\Scripts\python.exe -m streamlit run frontend/app.py
```

**怎么确认起来了**

- 后端：访问 http://127.0.0.1:8000/health，应返回
  `{"status":"ok","agent_ready":true,"tools":["web_search","search_car_docs"],"memory":true}`
- 前端：侧边栏显示「Agent 已就绪 · 工具：web_search、search_car_docs」+「多轮记忆：已启用」

不确定缺什么就先双击 `run_check.bat`（或 `python check_env.py`），它会逐项告诉你缺哪个包、哪个 key。

**启动不了先看这三条**

| 现象 | 原因 | 处理 |
|---|---|---|
| `Address already in use` | 8000/8501 被上一次没关的进程占着 | `netstat -ano \| findstr :8000` 找到 PID，`taskkill /PID <pid> /F` |
| 侧边栏「后端未连接」 | 后端没起，或起来时崩了 | 看后端那个终端窗口的最后几行报错 |
| 前端能开、一发消息就报错 | `.env` 没读到（key 为空）或 key 失效 | `backend/config.py` 启动时会 `load_dotenv(car_agent/.env)`，确认 `.env` 就在 `car_agent` 根目录、且 `ARK_API_KEY=` 后面没有重复写变量名 |

## 三、两种模式是自动切换的

- **Agent 模式**：`langchain` 可用且有工具时自动启用，模型会自己决定「查知识库 / 联网搜 / 直接答」
- **纯对话模式**：缺 langchain 或缺工具时自动降级，走原生 Ark SDK（就是你原来那份代码的逻辑）

侧边栏会显示当前模式，不会出现「跑不起来」的黑屏，方便你一步步加能力。

## 四、装依赖（用的 uv，因为这个环境没有 pip）

```
cd E:\python-project\PythonProject
uv pip install --python .venv\Scripts\python.exe fastapi uvicorn streamlit
uv pip install --python .venv\Scripts\python.exe -r car_agent\requirements-agent.txt
```

当前环境已有：langchain 1.4.9、langchain-openai、langchain-community、langchain-chroma、chromadb 1.5.9、langgraph + langgraph-checkpoint-sqlite、fastapi 0.162、uvicorn 0.54、streamlit 1.67、pypdf、tavily-python 0.8.5、sqlalchemy、requests、dotenv、arkruntime。
阶段 5 的记忆库是 SQLite，Python 标准库自带，不需要额外装东西。

注意 `langchain` 必须是 1.x，`create_agent` 在 1.0 才提供；0.3.x 需要先升级。

## 五、阶段 3：联网搜索（已通）

1. 去 tavily.com 注册拿 key，填到 `.env` 的 `TAVILY_API_KEY`
2. 重启后端，`/health` 的 tools 里应出现 `web_search`
3. 问「今年新上市的 20 万级纯电 SUV 有哪些」，侧边栏上方会出现「正在调用 web_search」

## 六、阶段 4：知识库（已通）

当前语料是 **3 份厂商官方使用说明书，共 868 页 / 约 61 万字**，切出 2092 个片段：

| 车型 | 页数 | 文件 |
|---|---|---|
| 问界M7 | 227 | `问界M7_使用说明书.pdf` |
| 问界M9（2025 款增程） | 440 | `问界M9_2025款增程版_使用说明书.pdf` |
| 赛力斯SF5 | 201 | `赛力斯SF5_使用说明书.pdf` |

PDF 不进仓库（体积 + 版权），clone 后跑一次即可复现：

```bash
python fetch_docs.py                    # 下载语料
python -m backend.rag.ingest --reset    # 建库（先停掉后端）
```

再放自己的资料（支持 `.pdf` / `.md` / `.txt`）就重复上面第二条。

### 两个检索质量的关键设计

**1. 元数据按车型过滤**

`ingest.py` 从文件名识别车型，写进 `metadata["车型"]`；`search_car_docs` 收到问题后先提取车型
（`问界M7` / `M9` / `赛力斯SF5`），命中就加 `where={"车型": {"$in": [...]}}` 限定范围。

这一步很关键：不加固前问「问界M7多久保养一次」，top-1 返回的是 **M9** 的保养周期表——两份手册措辞高度相似，纯语义检索分不清车型。

指定车型没命中时会自动退回全库检索，不会因为元数据缺失就空手而归。

**2. 过滤封面/前言/版权页**

每份手册前几页都是「感谢您选择…版权归赛力斯汽车有限公司所有」，词面上和任何问题都能沾点边，
之前问「胎压」top-1 返回的就是前言。现在按「页序 < 4 且命中套话关键词」或「提取文字 < 40 字」丢弃。

### 切分策略（`ingest.py` 里可调）

- PDF 按页加载，页内再用 `RecursiveCharacterTextSplitter` 切，默认 400 字 / 重叠 60 字
- Markdown 先按 `##` 标题切（「一节 = 一个语义块」，表格不被截断），超长再递归切
- 中文分隔符包含 `。！？；，`，避免按空格切

向量化：配了 `DASHSCOPE_API_KEY` 走百炼 `text-embedding-v4`（1024 维），否则回落方舟 embedding。
**百炼单次最多 10 条**，所以 `embedding.py` 里 `chunk_size=10`，超过会报
`batch size is invalid, it should not be larger than 10`。**换模型必须重建库**。

### 为什么用 Chroma 不用 FAISS

FAISS 的 LangChain 封装在 `langchain-community` 里，而该包官方已宣布 sunset（停止积极维护）。Chroma 有独立 partner 包 `langchain-chroma`，并且支持持久化、按 id 增删改、`where` 元数据过滤——改文档时不用整库重建。FAISS 更适合数据量大、需要手工调 IVF/HNSW 参数的场景。

`rag/base.py` 定的是抽象接口，想换成 FAISS / Milvus，只要新增一个实现类、改 `rag/__init__.py` 一行，上层代码不用动。

## 七、阶段 5：多轮记忆（已通）

会话上下文交给 LangGraph 的 `SqliteSaver` 管理，落在 `data/agent_memory.db`，**和前端那套会话 JSON 分工明确**：

| | 前端 JSON（`data/sessions/`） | SqliteSaver（`data/agent_memory.db`） |
|---|---|---|
| 存什么 | 界面上显示的对话、会话列表 | Agent 的完整运行状态（消息 + 工具调用） |
| 谁读 | Streamlit 侧边栏、历史回看 | 只喂给模型 |
| 键 | 文件名 | `thread_id`（= 会话名） |

关键点是**前端只发最新一条消息**：

```python
# frontend/app.py
json={"messages": messages[-1:], "session_id": session_id}
```

历史由 checkpointer 按 `thread_id` 恢复，后端不再每轮接收全量上下文，省 token 也省解析。

实现要点（`backend/agent_core.py`）：

```python
connection = sqlite3.connect(path, check_same_thread=False)  # FastAPI 跑在线程池里
checkpointer = SqliteSaver(connection)
checkpointer.setup()                                        # 建表，漏了会报 no such table

create_agent(
    model=llm, tools=tools,
    system_prompt=CAR_EXPERT_PROMPT,
    checkpointer=checkpointer,
    middleware=[SummarizationMiddleware(          # 历史过长自动压缩
        model=llm,
        trigger=("messages", 20),                 # MEMORY_TRIGGER
        keep=("messages", 10),                    # MEMORY_KEEP
    )],
)
```

四个容易踩的点：

1. **`setup()` 必须调用**，重复调无害，但不调会 `no such table: checkpoints`
2. **`stream_mode` 保持 `"messages"`**，改成 `"values"` 会把恢复的历史整段重播，前端看到历史刷两遍
3. **降级路径仍要靠全量 messages**：`_stream_plain()` 走原生 SDK，没有 checkpointer，所以 `stream_chat(messages, session_id)` 两个参数都要传
4. **会话 id 不能重名**：id 同时是 `thread_id`，`new_session()` 用「时间戳 + 6 位随机后缀」防止同一秒撞车

## 八、`.env` 写法三条硬规矩

```ini
ARK_API_KEY=ark-xxxx          # 对：等号左边只写一次变量名
# ARK_API_KEY=ARK_API_KEY=ark-xxxx   # 错：变量名写重了，值会带上前缀，401
TAVILY_API_KEY="tvly-dev-xxx"  # 可加引号，但结尾不能有逗号
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# EMBEDDING_BASE_URL=...,     # 错：结尾逗号会让 dotenv 解析失败
```

## 九、常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 侧边栏提示后端未连接 | 后端没启动或端口被占 | 先跑 `run_backend.bat`，确认 8000 端口空闲 |
| 一直纯对话模式 | langchain 不在当前解释器里 | 两个 bat 里的 `PYTHON_EXE` 指向装 langchain 的那个环境 |
| 回复乱码 | 终端编码 | bat 里已设 `chcp 65001`，仍乱码就把终端换 UTF-8 |
| Agent 报工具错误 | Tavily key 无效 | `/health` 里看 tools，缺 key 时工具会返回提示而不是崩掉 |
| `database is locked` | 后端还开着，又跑了 ingest | 先停后端，再建库 |
| `batch size is invalid ... larger than 10` | 百炼 embedding 单批上限 10 | `embedding.py` 里已设 `chunk_size=10` |
| `TimeoutError: Request timed out` | 模型请求超过时限（联网搜索/长回答常超过 60s） | `.env` 里调大 `LLM_TIMEOUT`（默认 180），重启后端 |
| 检索答成别的车型 | 问题里没带车型名，或文件名没按 `问界M*` / `赛力斯SF*` 命名 | 提问带上车型；新语料按规范命名后 `--reset` 重建 |
| 检索结果答非所问 | 切分太粗 / 语料太少 | 小标题切分、缩小 chunk、增加语料，或加大 top-k |
| 模型不记得上一轮说的 | 会话 id 变了，或用的是加 checkpointer 之前的旧会话 | 看侧边栏「多轮记忆：已启用」；旧 JSON 没有对应 checkpoint，新建会话重来 |
| `no such table: checkpoints` | 漏了 `checkpointer.setup()` | 已内置，若手动改过代码检查这一行 |
| 记忆库删不掉 | 后端还占着文件 | 先停后端，再删 `data/agent_memory.db` |

## 十、放 GitHub 前的检查清单

- [ ] `.env` 没被提交（`.gitignore` 已排除，仍要 `git status` 确认一遍）
- [ ] `data/chroma/`、`data/sessions/`、`data/agent_memory.db`、`data/docs/*.pdf` 没提交
- [ ] 确认 `python fetch_docs.py` 能拉到语料（别人 clone 后能复现）
- [ ] README 里补一张架构图（后端 → Agent → 工具 → 向量库）
- [ ] 录一段 30 秒 GIF：提问 → 看到「正在调用 search_car_docs」→ 带来源的答案
- [ ] 写清局限：单机向量库、无鉴权、无并发压测、记忆是单机 SQLite

面试时值得讲的四个点：

1. **为什么 SSE 不用 WebSocket**——单向流式够用，实现更简单，还支持 HTTP/1.1
2. **为什么先查知识库再联网**——提示词里写死了优先级，知识库有权威数据时不该让网页噪音干扰
3. **RAG 效果怎么评估**——准备 20 条「问题 → 应命中文档」的问答对，统计 top-4 命中率；命中率低就调切分和 top-k
4. **多轮记忆为什么用 checkpointer 不用会话表**——前端只传增量、历史由 `thread_id` 恢复，且业务展示层与上下文层解耦；换 Postgres Saver 或加 `sessions` 表都不影响上层
