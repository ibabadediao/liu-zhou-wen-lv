import os
from abc import ABC, abstractmethod
from typing import Optional

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from utils.config_handler import rag_config


"""
模型工厂类
"""

# DashScope 的 OpenAI 兼容模式端点
# 注意: qwen3.8 / deepseek-v4.1-flash 等模型仅在该接口提供, 旧的原生 Generation 接口会报"url error"
DASHSCOPE_COMPATIBLE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 基础模型工厂类
class BaseModelFactory(ABC):
    @abstractmethod   # 抽象方法，用于创建模型
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass

# 聊天模型工厂类
class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return ChatOpenAI(
            model = rag_config['chat_model_name'],
            api_key = os.environ['DASHSCOPE_API_KEY'],
            base_url = DASHSCOPE_COMPATIBLE_BASE_URL,
        )

# 嵌入模型工厂类
class EmbeddingModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return DashScopeEmbeddings(model = rag_config['embedding_model_name'])

# 创建聊天模型实例 (deepseek-v4.1-flash 原生支持视觉, 不再需要独立 vision_model)
chat_model = ChatModelFactory().generator()
# 创建嵌入模型实例
embedding_model = EmbeddingModelFactory().generator()
