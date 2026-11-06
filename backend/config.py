"""全局配置：所有密钥、模型名、路径都从这里读，禁止在业务代码里写死。"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")#__file__是当前文件意思,.resolve()是转绝对路径,.parent是返回上一级


class Settings:
    def __init__(self) -> None:
        self.ark_api_key: str = os.getenv("ARK_API_KEY", "")
        self.ark_base_url: str = os.getenv(
            "ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
        )
        self.ark_model: str = os.getenv("ARK_MODEL", "doubao-seed-2-1-lite-260915")

        self.tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")

        # 阶段 4 建知识库时用，走火山方舟的 embedding 接口
        self.embedding_model: str = os.getenv(
            "EMBEDDING_MODEL", "text-embedding-v4"
        )
        # 配上百炼 key 就走 DashScope，没配才回落到方舟
        self.dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
        self.embedding_base_url: str = os.getenv(
            "EMBEDDING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

        # 1 = 尝试用 LangChain Agent（装了 langchain 才生效），0 = 强制纯对话
        self.use_agent: bool = os.getenv("USE_AGENT", "1") == "1"

        # 模型请求超时（秒）。联网搜索 + 长回答经常超过 60s，
        # 太短会直接 TimeoutError，然后被迫退回纯对话。
        self.llm_timeout: int = int(os.getenv("LLM_TIMEOUT", "180"))

        self.docs_dir: Path = ROOT / "data" / "docs"
        self.chroma_dir: Path = ROOT / "data" / "chroma"
        self.sessions_dir: Path = ROOT / "data" / "sessions"

        # LangGraph checkpointer 的落盘位置：存 Agent 的上下文，和前端会话 JSON 互不相干
        self.memory_db_path: Path = ROOT / "data" / "agent_memory.db"
        # 摘要压缩阈值：历史消息超过 trigger 条就交给模型压缩，只留 keep 条原文
        self.memory_trigger: int = int(os.getenv("MEMORY_TRIGGER", "20"))
        self.memory_keep: int = int(os.getenv("MEMORY_KEEP", "10"))

    def ensure_dirs(self) -> None:
        for d in (self.docs_dir, self.sessions_dir, self.memory_db_path.parent):
            d.mkdir(parents=True, exist_ok=True)#parents=True表示如果父目录不存在则创建，exist_ok=True表示如果目录存在则不报错


settings = Settings()
