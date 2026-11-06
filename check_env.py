"""一键体检：告诉你现在缺什么、下一步该做什么。

用法（在 car_agent 目录下）：
    python check_env.py
"""

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass


def has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except Exception:
        return False


OK, NO = "[OK]  ", "[缺失]"

print("=" * 62)
print(f"Python 解释器：{sys.executable}")
print(f"版本：{sys.version.split()[0]}")
print("=" * 62)

checks = [
    ("fastapi", "FastAPI 框架", True),
    ("uvicorn", "ASGI 服务器", True),
    ("streamlit", "前端界面", True),
    ("arkruntime", "火山方舟 SDK（纯对话兜底）", True),
    ("requests", "前端请求后端", True),
    ("langchain.agents", "LangChain Agent 核心", False),
    ("langchain_openai", "LangChain 的 OpenAI 兼容层", False),
    ("langchain_core", "LangChain 基础包", False),
    ("tavily", "联网搜索（阶段 3）", False),
    ("chromadb", "Chroma 向量库（阶段 4）", False),
    ("langchain_chroma", "Chroma 的 LangChain 适配（阶段 4）", False),
    ("pypdf", "PDF 文档加载（阶段 4）", False),
]

missing_required, missing_optional = [], []
for module, label, required in checks:
    ok = has(module)
    print(f"{OK if ok else NO} {label:<28} ({module})")
    if not ok:
        (missing_required if required else missing_optional).append(module)

print("-" * 62)
print("环境变量：")
for key, hint in [
    ("ARK_API_KEY", "必须，火山方舟密钥"),
    ("TAVILY_API_KEY", "阶段 3 需要"),
    ("ARK_MODEL", "可选，默认 doubao-seed-2-1-lite-260915"),
]:
    value = os.getenv(key, "")
    shown = (value[:6] + "…" + value[-4:]) if len(value) > 12 else ("(空)" if not value else "***")
    print(f"  {'[有]' if value else '[无]'} {key:<16} {shown:<18} {hint}")

print("-" * 62)
try:
    import requests

    r = requests.get("http://127.0.0.1:8000/health", timeout=3)
    info = r.json()
    print(f"后端状态：在线 · 模型 {info.get('model')}")
    print(f"          Agent {info.get('agent_ready')} · 工具 {info.get('tools')}")
    print(f"          多轮记忆 {info.get('memory')}")
    if info.get("memory_note"):
        print(f"          记忆说明：{info['memory_note']}")
    if info.get("reason"):
        print(f"          说明：{info['reason']}")
except Exception:
    print("后端状态：未启动（先运行 run_backend.bat）")

print("=" * 62)
print("下一步：")
step = 1
if not os.getenv("ARK_API_KEY"):
    print(f"  {step}. 打开 car_agent/.env，把 ARK_API_KEY= 后面填上密钥"); step += 1
if missing_required:
    print(f"  {step}. 当前环境缺少：{', '.join(missing_required)}"); step += 1
if missing_optional:
    print(f"  {step}. 可选依赖未装：{', '.join(missing_optional)}（不影响当前功能）"); step += 1
print(f"  {step}. 启动后端：PyCharm 运行配置「car_agent 后端 (8000)」或 run_backend.bat")
print(f"  {step + 1}. 启动前端：PyCharm 运行配置「car_agent 前端 (8501)」或 run_frontend.bat")
