"""Agent 核心。

对外只暴露一个 stream_chat()，产出统一的事件字典：
    {"type": "mode",  "mode": "agent" | "plain", "reason": "..."}
    {"type": "token", "content": "文字片段"}
    {"type": "tool",  "name": "web_search"}
    {"type": "error", "message": "..."}

装了 langchain 且有可用工具 -> 走 Agent；否则自动降级成纯对话，
保证任何一步都不会卡住整个项目。

多轮记忆：LangGraph 的 SqliteSaver 按 thread_id（= 会话名）存 Agent 状态，
前端只发最新一条消息，历史由 checkpointer 恢复。
"""

import re
import sqlite3
import threading
import uuid
from typing import Iterator

from .config import settings
from .llm import get_ark_client, get_langchain_llm
from .prompts import CAR_EXPERT_PROMPT

_agent = None
_tools = []
_agent_error: str | None = None
_agent_ready = False

_checkpointer = None
_checkpointer_error: str | None = None
_memory_note = ""
_lock = threading.Lock()


# ============ 【课里没有】流式文本过滤 ============
# 豆包偶尔不按"标准工具调用通道"来，而是把调用写进正文里，比如：
#     <FunctionCallBegin>[{"name":"web_search",...}]<FunctionCallEnd>
# 不处理的话，用户会在聊天框里看到这坨原始协议文本。
#
# 麻烦点在于流式输出：这一串可能被切成好几个小片段（chunk），
# 所以不能只对每个片段单独做替换——标记的开头和结尾可能落在不同片段里。
# 做法：维护一个"攒字缓冲区"，识别到完整标记就丢掉，识别到"半个标记"就先攒着。
class _StreamCleaner:
    """把 <FunctionCallBegin>...<FunctionCallEnd> 从流式文本里剔除。"""

    OPEN, CLOSE = "<FunctionCallBegin>", "<FunctionCallEnd>"

    def __init__(self) -> None:
        self._pending = ""    # 尾部可能是半个标记，先攒着不输出
        self._hiding = False  # True = 正在标记内部，内容全部丢弃

    def feed(self, text: str) -> str:
        """喂进来一个新片段，返回该片段里"确定能安全输出"的部分。"""
        out = []
        self._pending += text
        while self._pending:
            if self._hiding:
                end = self._pending.find(self.CLOSE)
                if end == -1:
                    # 结尾可能只有半个 </FunctionCallEnd>，把那段攒起来
                    keep = self._tail_overlap(self.CLOSE)
                    self._pending = self._pending[len(self._pending) - keep:] if keep else ""
                    break
                self._pending = self._pending[end + len(self.CLOSE):]
                self._hiding = False
            else:
                start = self._pending.find(self.OPEN)
                if start == -1:
                    # 结尾可能是半个 <FunctionCallBegin>，同样攒起来
                    keep = self._tail_overlap(self.OPEN)
                    cut = len(self._pending) - keep
                    if cut > 0:
                        out.append(self._pending[:cut])
                        self._pending = self._pending[cut:]
                    break
                if start > 0:
                    out.append(self._pending[:start])
                self._pending = self._pending[start + len(self.OPEN):]
                self._hiding = True
        return "".join(out)

    def _tail_overlap(self, marker: str) -> int:
        """pending 结尾处与 marker 前缀重叠的长度（可能是半个标记）。"""
        for k in range(min(len(self._pending), len(marker) - 1), 0, -1):
            if self._pending.endswith(marker[:k]):
                return k
        return 0


def _load_tools():
    """按依赖是否就绪来挂工具，缺什么就跳过什么。"""
    tools, notes = [], []

    try:
        from .tools.web_search import web_search

        tools.append(web_search)
        if not settings.tavily_api_key:
            notes.append("web_search 已挂载但缺少 TAVILY_API_KEY")
    except Exception as exc:
        notes.append(f"web_search 不可用：{exc}")

    try:
        from .rag import store_ready
        from .tools.rag_search import search_car_docs

        if store_ready():
            tools.append(search_car_docs)
        else:
            notes.append("知识库未建立（data/chroma 不存在），search_car_docs 未挂载")
    except Exception as exc:
        notes.append(f"search_car_docs 不可用：{exc}")

    return tools, notes


def get_checkpointer():
    """SqliteSaver 单例：建连接 -> 初始化 -> 建表（对齐课程 2.6 的写法）。

    setup() 不能省，它负责创建 checkpoints / writes 两张表；
    连接必须 check_same_thread=False，因为 FastAPI 的同步接口跑在线程池里。
    """
    global _checkpointer, _checkpointer_error

    if _checkpointer is not None or _checkpointer_error is not None:
        return _checkpointer

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        settings.ensure_dirs()
        connection = sqlite3.connect(
            str(settings.memory_db_path), check_same_thread=False
        )
        saver = SqliteSaver(connection)
        saver.setup()  # 自动建表，重复调用无副作用
        _checkpointer = saver
    except Exception as exc:
        _checkpointer_error = f"SqliteSaver 初始化失败：{type(exc).__name__}: {exc}"

    return _checkpointer


def _summary_middleware(llm):
    """历史过长时自动压缩，避免 checkpoint 无限膨胀。"""
    from langchain.agents.middleware import SummarizationMiddleware

    return SummarizationMiddleware(
        model=llm,
        trigger=("messages", settings.memory_trigger),
        keep=("messages", settings.memory_keep),
    )


def get_agent():
    """懒加载单例，避免每次请求都重建。"""
    global _agent, _tools, _agent_error, _agent_ready, _memory_note

    with _lock:
        if _agent is not None or _agent_error is not None:
            return _agent

        if not settings.use_agent:
            _agent_error = "USE_AGENT=0，已手动关闭 Agent"
            return None

        try:
            from langchain.agents import create_agent
        except Exception as exc:
            _agent_error = f"未安装或版本不支持 create_agent：{exc}"
            return None

        tools, notes = _load_tools()
        if not tools:
            _agent_error = "没有可用工具，先退化为纯对话。原因：" + "；".join(notes)
            return None

        try:
            llm = get_langchain_llm()

            # 你的 langchain 是 1.4.9，create_agent 的三个参数都原生支持：
            #   system_prompt —— 人设（等价于课里 2.4prompt 那套）
            #   checkpointer  —— 多轮记忆（课里 2.6memory）
            #   middleware    —— 历史太长时自动摘要压缩
            # 所以这里直接写清楚，不用再"猜版本"。
            kwargs = {"system_prompt": CAR_EXPERT_PROMPT}

            checkpointer = get_checkpointer()
            if checkpointer is not None:
                kwargs["checkpointer"] = checkpointer
                kwargs["middleware"] = [_summary_middleware(llm)]
            else:
                _memory_note = _checkpointer_error or "checkpointer 不可用，无多轮记忆"

            # create_agent 就是把 model + tools + 上面这些配置打包成一个 Agent
            _agent = create_agent(model=llm, tools=tools, **kwargs)

            _tools = [t.name for t in tools]
            _agent_ready = True
            _agent_error = None
        except Exception as exc:
            _agent_error = f"Agent 构建失败：{type(exc).__name__}: {exc}"

        return _agent


def agent_status() -> dict:
    get_agent()
    return {
        "ready": _agent_ready,
        "tools": _tools,
        "reason": _agent_error,
        "memory": bool(_checkpointer is not None),
        "memory_note": _memory_note,
        "memory_db": str(settings.memory_db_path),
    }


# ===================== 【课里没有】yield 和 yield from =====================
# 这是整个项目里唯一一个"核心技术点"，看懂这两个就通了。
#
# yield：函数里有 yield，它就不再是普通函数，而是"生成器函数"。
#        调用它不会执行，只会返回一个生成器；for 循环每转一圈，它才往下跑一段，
#        跑到 yield 就把这个值交出来、然后停在原地等你下次再要。
#
#        写法对比（就这一个区别）：
#            def f():            def f():
#                return [1,2,3]      yield 1
#                                    yield 2
#                                    yield 3
#        左边要攒齐整份才给你；右边要一个给一个。—— 这就是"流式"的本质。
#
# yield from：把另一个生成器的产出原样转发出去，等于少写一层 for。
#            yield from g()  等价于  for x in g(): yield x
#
# 这里的 stream_chat 就是一个生成器：调用方（main.py）每要一次，
# 它就从模型那里取一小段文字、包成一个 dict 交出去。
# 四种 dict 就是前后端约定的"暗号"，前端只认这四个 type：
#     mode  = 本次走的是 agent 还是纯对话
#     token = 一小段文字（前端拼起来显示）
#     tool  = 正在调用哪个工具（前端显示"正在检索知识库"）
#     error = 出错了（前端红字提示）
# ==========================================================================
def stream_chat(
    messages: list[dict], session_id: str | None = None
) -> Iterator[dict]:
    """messages 是 [{"role": "user"/"assistant", "content": "..."}] 的完整历史。

    session_id 用作 LangGraph 的 thread_id：
        - Agent 路径只用 messages[-1]，历史由 checkpointer 按 thread_id 恢复
        - 兜底路径没有 checkpointer，必须依赖完整 messages
    """
    agent = get_agent()
    # session_id 可能是 None（比如 /docs 里手点测试），
    # 但 LangGraph 要求必须有 thread_id，所以兜底生成一个随机串。
    thread_id = session_id or uuid.uuid4().hex

    if agent is None:
        # 没有 Agent 就降级：先把原因告诉前端，再走原生 SDK 纯对话
        yield {"type": "mode", "mode": "plain", "reason": _agent_error or ""}
        yield from _stream_plain(messages)
        return

    yield {"type": "mode", "mode": "agent", "reason": ""}
    try:
        yield from _stream_with_agent(agent, messages, thread_id)
    except Exception as exc:
        # 超时是最常见的错误，顺手告诉用户去哪里调
        timed_out = "timed out" in str(exc).lower() or isinstance(exc, TimeoutError)
        hint = "。可在 .env 里调大 LLM_TIMEOUT（当前 %d 秒）" % settings.llm_timeout if timed_out else ""
        yield {
            "type": "error",
            "message": f"Agent 运行出错（{type(exc).__name__}: {exc}），已退回纯对话{hint}。",
        }
        yield from _stream_plain(messages)


def _stream_with_agent(agent, messages: list[dict], thread_id: str) -> Iterator[dict]:
    from langchain_core.messages import AIMessageChunk

    # 人设已经在 create_agent(system_prompt=...) 里配好了，
    # 所以这里只发"这一条新消息"，历史由 checkpointer 恢复。
    latest = dict(messages[-1])
    latest["id"] = uuid.uuid4().hex

    payload = {"messages": [latest]}

    config = {"configurable": {"thread_id": thread_id}}

    seen_tools: set[str] = set()
    cleaner = _StreamCleaner()
    for chunk, _meta in agent.stream(payload, config=config, stream_mode="messages"):
        if not isinstance(chunk, AIMessageChunk):
            continue

        for call in chunk.tool_call_chunks or []:
            name = call.get("name")
            if name and name not in seen_tools:
                seen_tools.add(name)
                yield {"type": "tool", "name": name}

        text = chunk.content
        if isinstance(text, list):
            text = "".join(
                part.get("text", "")
                for part in text
                if isinstance(part, dict) and part.get("type") in (None, "text")
            )
        if text:
            cleaned = cleaner.feed(text)
            if cleaned:
                yield {"type": "token", "content": cleaned}


def _stream_plain(messages: list[dict]) -> Iterator[dict]:
    """兜底路径：走原生 Ark SDK，也就是你原来那份代码的逻辑。"""
    client = get_ark_client()
    cleaner = _StreamCleaner()
    response = client.responses.create(
        model=settings.ark_model,
        input=[{"role": "system", "content": CAR_EXPERT_PROMPT}, *messages],
        stream=True,
    )
    for chunk in response:
        if getattr(chunk, "type", None) == "response.output_text.delta":
            delta = getattr(chunk, "delta", "")
            if delta:
                cleaned = cleaner.feed(delta)
                if cleaned:
                    yield {"type": "token", "content": cleaned}
