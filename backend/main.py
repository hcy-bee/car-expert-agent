"""FastAPI 入口。

启动：python -m uvicorn backend.main:app --reload --port 8000
文档：http://127.0.0.1:8000/docs

================================ 阅读提示 ================================
这个文件里大部分写法和你 FastAPIProject 里的五个文件是一样的：
@ 装饰器、路径/查询参数、BaseModel、HTTPException、返回 dict。

只有三处是课里没讲过的，都在代码里标了【课里没有】：
  1. CORS 中间件      —— 前后端不同端口，浏览器会拦，必须放开
  2. yield 生成器     —— 有 yield 的函数不会一次跑完，而是"挤一点给一点"
  3. StreamingResponse —— 配合生成器，实现"字一个个蹦出来"的流式输出
==========================================================================
"""

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .agent_core import agent_status, stream_chat
from .config import settings

app = FastAPI(title="汽车专家 Agent API", version="0.2.0")

# 【课里没有】CORS 中间件
# 前端跑在 8501，后端跑在 8000，浏览器认为这是"两个不同的网站"，
# 默认不让它们互相通信。这个中间件的作用就是给每个响应加几个
# Access-Control-Allow-* 响应头，告诉浏览器"允许它跨域访问"。
# 本地练习可以写 "*"，正式上线要改成具体域名。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: str = Field(description="user 或 assistant")
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    session_id: str | None = None


# 【课里没有】SSE 协议的格式约定
# SSE（Server-Sent Events）是一种"服务器单向往浏览器滴数据"的格式，
# 规矩只有两条：
#   1. 每条消息必须以 "data: " 开头（注意冒号后面有一个空格）
#   2. 每条消息结尾必须是两个换行，用来告诉浏览器"这条结束了、下一条开始"
# 少写 "data: " 或者少写一个换行，前端就一行都收不到，这是最常见的坑。
#
# ensure_ascii=False 是为了让中文原样输出；不加的话"汽车"会变成 \u6c7d\u8f66，
# 前端虽然也能解析，但你自己用 curl 调试时完全看不懂。
def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.get("/health")
def health() -> dict:
    status = agent_status()
    return {
        "status": "ok",
        "model": settings.ark_model,
        "agent_ready": status["ready"],
        "tools": status["tools"],
        "reason": status["reason"],
        "memory": status["memory"],
        "memory_note": status["memory_note"],
    }


# ===================== 【课里没有】流式响应，这段最值得看懂 =====================
# 你课里的接口都是这个形状：
#       @app.get("/xxx")
#       async def f():
#           return {"a": 1}          # 函数全部跑完，才一次性返回
# 这种写法下，模型要生成 300 字得等十几秒，页面就是白屏十几秒。
#
# 想让它"字一个个蹦出来"，就要换成"生成器 + 流式响应"：
#
#   ① 函数里用 yield 代替 return
#      —— 有 yield 的函数叫"生成器函数"。调用它并不会真的执行，
#         只是返回一个生成器对象；每被要一次（for 循环就是在要），
#         才往下跑一小段，跑到 yield 就把值交出去、然后冻住等你下次要。
#      类比：return 是"整桌菜做好了才一起端上来"，
#            yield 是"做好一道就先端一道"，客人不用干等。
#
#   ② StreamingResponse 收到这个生成器后，每挤出一个值就立刻写回浏览器，
#      不等函数结束。media_type="text/event-stream" 就是 SSE 的标准类型。
#
# 为什么用 def 而不是你熟悉的 async def：
#   这里调用的 langchain / ark SDK 都是"同步阻塞"的。写在 async def 里会卡住
#   整个事件循环（所有请求一起卡）；写成普通的 def，FastAPI 会自动把它丢到
#   线程池执行，阻塞只影响它自己。所以这里 def 是故意的，不是写错了。
#
# 为什么 try/except 要包在生成器里面：
#   第一次 yield 时，HTTP 200 和响应头就已经发给浏览器了，之后出错不可能再改成
#   500。只能在流里追加一条 error 事件，让前端自己显示"出错了"。
# =============================================================================
@app.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    """流式对话：SSE 逐条推送 mode / token / tool / done 事件。"""

    # model_dump() 是 Pydantic v2 的方法，把 Message 对象变成普通 dict，
    # 等价于旧版的 .dict()；这样下游的 stream_chat 只处理 dict，不用管 Pydantic。
    messages = [m.model_dump() for m in req.messages]

    # 这里是一个"嵌套函数"，定义在 chat 里面，所以能直接用外层的 messages 和 req。
    # 它自己不 return，而是一路 yield —— 它就是一个生成器。
    def event_stream():
        try:
            # stream_chat 也是生成器（在 agent_core.py 里），
            # "生成器套生成器"用 for 循环取，取到一个就打包成 SSE 一行推出去。
            for event in stream_chat(messages, req.session_id):
                yield _sse(event)
        except Exception as exc:
            yield _sse({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        # 没有 done 这条，前端不知道"流结束了"，会一直等下去
        yield _sse({"type": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        # 两个 header 都是防缓存的：有些代理会把流式响应攒起来再一起发，
        # 那就完全失去流式的意义了。
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/chat/sync")
def chat_sync(req: ChatRequest) -> dict:
    """非流式版本，方便 curl / Postman 调试。

    它和上面的 /chat 用的是同一个 stream_chat，区别只在于：
    /chat 边取边推给浏览器；这里是用 for 循环把流"攒"起来，
    攒完之后一次性 return。所以这个接口的写法跟你课里学的完全一样。
    """
    messages = [m.model_dump() for m in req.messages]
    text, tools, mode = "", [], ""
    for event in stream_chat(messages, req.session_id):
        if event["type"] == "token":
            text += event["content"]
        elif event["type"] == "tool":
            tools.append(event["name"])
        elif event["type"] == "mode":
            mode = event["mode"]
        elif event["type"] == "error":
            return {"ok": False, "mode": mode, "error": event["message"], "content": text}
    return {"ok": True, "mode": mode, "tools": tools, "content": text}
