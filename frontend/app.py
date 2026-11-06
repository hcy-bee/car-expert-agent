"""Streamlit 前端：只负责界面，所有对话逻辑都在 FastAPI 后端。

启动：streamlit run frontend/app.py
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st

BACKEND = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
SESSION_DIR = Path(__file__).resolve().parent.parent / "data" / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="汽车专家 Agent", page_icon="🚗", layout="wide")


# ---------- 会话存取 ----------
def save_session() -> None:
    data = {"messages": st.session_state.messages, "current": st.session_state.current}
    with open(SESSION_DIR / f"{st.session_state.current}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_sessions() -> list[str]:
    files = [p.stem for p in SESSION_DIR.glob("*.json")]
    return sorted(files, reverse=True)


def load_session(name: str) -> None:
    # try/except 和你原代码 load_sessions 里的写法一样：
    # 某个会话文件损坏时，只报这一条错误，不让整个页面崩掉。
    try:
        with open(SESSION_DIR / f"{name}.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        st.error("加载会话错误")
        return
    st.session_state.messages = data.get("messages", [])
    st.session_state.current = data.get("current", name)


def delete_session(name: str) -> None:
    (SESSION_DIR / f"{name}.json").unlink(missing_ok=True)


def new_session() -> None:
    # 只清空 + 换新 id，【故意不保存旧会话】—— 对齐你原代码的语义：
    # "保存旧会话"是"新建会话"按钮的动作，不是这个函数的职责。
    # 删除当前会话时也会走到这里，如果在函数里自动保存，
    # 会把刚删掉的文件原样写回磁盘，造成"删不掉"的假象。
    st.session_state.messages = []
    st.session_state.current = make_session_id()


def make_session_id() -> str:
    """会话 id 同时是 thread_id：时间戳便于阅读，随机后缀防止同一秒重名。"""
    return f"{datetime.now():%Y-%m-%d %H-%M-%S}-{uuid.uuid4().hex[:6]}"


# ---------- 后端通信 ----------
def check_backend() -> dict | None:
    try:
        r = requests.get(f"{BACKEND}/health", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def stream_backend(messages: list[dict], session_id: str):
    """只发最新一条消息 + 会话 id，历史由后端的 checkpointer 按 thread_id 恢复。

    这个函数也是生成器（有 yield）。它干的事就是"读后端的 SSE 流"：
      stream=True      -> 让 requests 不要一次读完整个响应，而是边收边给
      iter_lines()     -> 一行一行地交给我们
      去掉 "data: "    -> 后端的每条消息都以这个前缀开头，去掉之后剩下的才是 JSON
      最后 yield 出来  -> 交给界面那边边收边显示
    """
    resp = requests.post(
        f"{BACKEND}/chat",
        json={"messages": messages[-1:], "session_id": session_id},
        stream=True,
        timeout=(10, 300),
    )
    resp.raise_for_status()
    for raw in resp.iter_lines(decode_unicode=False):
        if not raw:
            continue
        # 故意用 decode_unicode=False 再手动按 utf-8 解：
        # requests 遇到 text/event-stream 会默认按 ISO-8859-1 解，中文会变乱码。
        line = raw.decode("utf-8", errors="ignore")
        if line.startswith("data: "):
            # line[6:] 就是去掉前面 6 个字符 "data: "，剩下的是 JSON 字符串
            yield json.loads(line[6:])


# ---------- 状态初始化 ----------
st.session_state.setdefault("messages", [])
st.session_state.setdefault("current", make_session_id())
st.session_state.setdefault("mode_note", "")

# ---------- 侧边栏 ----------
with st.sidebar:
    st.subheader("服务状态")
    info = check_backend()
    if info is None:
        st.error("后端未连接，请先启动 FastAPI（8000 端口）")
    elif info.get("agent_ready"):
        st.success(f"Agent 已就绪 · 工具：{'、'.join(info['tools'])}")
        if info.get("memory"):
            st.caption("多轮记忆：已启用（SQLite checkpointer）")
        elif info.get("memory_note"):
            st.caption(info["memory_note"])
    else:
        st.warning("当前为纯对话模式")
        if info.get("reason"):
            st.caption(info["reason"])

    if st.button("重新检测", width="stretch"):
        st.rerun()

    st.divider()
    if st.button("新建会话", width="stretch", icon="✏️"):
        # 保存旧会话放在按钮里（和你原代码"新建会话"按钮一模一样），
        # 不放进 new_session()——原因见函数内注释
        if st.session_state.messages:
            save_session()
        new_session()
        st.rerun()

    st.text("会话历史")
    for name in list_sessions():
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(
                name,
                width="stretch",
                icon="📝",
                key=f"load_{name}",
                type="primary" if name == st.session_state.current else "secondary",
            ):
                load_session(name)
                st.rerun()
        with col2:
            if st.button("", width="stretch", icon="❌", key=f"del_{name}"):
                delete_session(name)
                if name == st.session_state.current:
                    new_session()
                st.rerun()

# ---------- 主区域 ----------
st.title("🚗 汽车专家 Agent")
st.caption(f"会话：{st.session_state.current}")
if st.session_state.mode_note:
    st.caption(st.session_state.mode_note)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("问车型、参数、保养、故障、选车建议…")

# ========== 两段式：先让会话上侧栏，再生成回答 ==========
# 你原代码（05.AI_partner_3.py）回答是秒回的，所以"回答完再 rerun"感觉不到延迟。
# 现在 Agent 回答要十几秒（思考 + 调工具），如果等回答完侧栏才更新，
# 你会觉得"发了半天消息侧栏没动静"。所以拆成两段：
#   第一段：消息一进来就写盘 + rerun —— 重跑后侧栏立刻扫到这个新会话
#   第二段：重跑后从 pending_prompt 里把问题捡回来，开始流式回答
# （不把问题存进 session_state 就 rerun 的话，chat_input 会被清空，回答就丢了。）
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_session()  # 立刻落盘：现在文件里只有问题，回答还没有，没关系
    st.session_state.pending_prompt = prompt
    st.rerun()

# ---------- 第二段：处理上一轮存下来的问题 ----------
pending = st.session_state.pop("pending_prompt", None)
if pending:
    # 用户消息不用再画一次：rerun 后上面的历史循环已经把它渲染出来了
    with st.chat_message("assistant"):
        tool_box = st.empty()
        text_box = st.empty()
        answer, tools = "", []

        try:
            for event in stream_backend(
                st.session_state.messages, st.session_state.current
            ):
                etype = event.get("type")
                if etype == "token":
                    answer += event.get("content", "")
                    text_box.markdown(answer + "▌")
                elif etype == "tool":
                    tools.append(event.get("name", ""))
                    tool_box.caption("🔧 正在调用：" + "、".join(dict.fromkeys(tools)))
                elif etype == "mode":
                    # 后端开头会报一次自己走的是哪条路。
                    # agent = 正常；plain = 降级成了纯对话，reason 里带原因。
                    # 存起来，主区域标题下面会显示，否则用户永远不知道降级了
                    if event.get("mode") == "plain":
                        reason = event.get("reason", "")
                        st.session_state.mode_note = (
                            "⚠️ 本轮已退回纯对话（无工具、无知识库）"
                            + (f"：{reason}" if reason else "")
                        )
                    else:
                        st.session_state.mode_note = ""
                elif etype == "error":
                    st.warning(event.get("message", ""))
        except Exception as exc:
            st.error(f"请求后端失败：{type(exc).__name__}: {exc}")

        text_box.markdown(answer or "（没有返回内容）")

    if answer:
        st.session_state.messages.append({"role": "assistant", "content": answer})
        save_session()
        # 注意这里不再 st.rerun()：
        #   1. 侧栏的即时刷新在第一段（发消息时）已经完成了，这里没必要再跑
        #   2. 一旦 rerun，页面只按 messages 重建，"🔧 正在调用"的提示
        #      会被清掉——留着不跑，这个提示就能一直挂在回答上方
        # 下一轮你发新消息触发 rerun 时，历史循环照样能渲染出完整回答。
