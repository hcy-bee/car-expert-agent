"""向量化模型。建库和查询必须用同一个模型，否则检索结果全错。

两条路（自动选择）：
1. 配了 DASHSCOPE_API_KEY -> 走阿里百炼 text-embedding-v4
2. 没配 -> 走火山方舟自带的 embedding
"""

from ..config import settings

_embeddings = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        from langchain_openai import OpenAIEmbeddings

        if settings.dashscope_api_key:
            api_key = settings.dashscope_api_key
            base_url = settings.embedding_base_url
        else:
            api_key = settings.ark_api_key
            base_url = settings.ark_base_url

        _embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=api_key,
            base_url=base_url,
            check_embedding_ctx_length=False,
            # 百炼 text-embedding-v4 单次最多 10 条，超过会报
            # "batch size is invalid, it should not be larger than 10"
            chunk_size=10,
        )
    return _embeddings
