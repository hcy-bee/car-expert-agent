"""模型接入层：一边给 LangChain 用，一边给原生 SDK 兜底用。"""

from .config import settings


def get_ark_client():
    """原生 SDK 客户端（兜底路径用，也是你原来那份代码的方式）。"""
    from arkruntime import Ark

    if not settings.ark_api_key:
        raise RuntimeError(
            "没有读到 ARK_API_KEY，请检查项目根目录下的 .env 文件是否配置正确。"
        )
    # timeout 不设的话走 SDK 默认（较短），联网/长回答容易超时报错，这里显式调长。
    return Ark(
        base_url=settings.ark_base_url,
        api_key=settings.ark_api_key,
        timeout=settings.llm_timeout,
    )


def get_langchain_llm():
    """给 LangChain Agent 用的模型（写法对齐课程 2.6memory.ipynb）。

    init_chat_model 会根据 model_provider 自动挑对应的集成类，
    火山方舟兼容 OpenAI 协议，所以 provider 写 "openai" 指过去就行。
    """
    from langchain.chat_models import init_chat_model

    if not settings.ark_api_key:
        raise RuntimeError(
            "没有读到 ARK_API_KEY，请检查项目根目录下的 .env 文件是否配置正确。"
        )
    return init_chat_model(
        model=settings.ark_model,
        model_provider="openai",
        base_url=settings.ark_base_url,
        api_key=settings.ark_api_key,
        temperature=0.3,
        # ChatOpenAI 的超时参数：每次调模型最多等这么久（秒）。
        # 注意这是"一次模型请求"的超时，Agent 一次回答里调多次模型，每次各有 180s。
        timeout=settings.llm_timeout,
    )
