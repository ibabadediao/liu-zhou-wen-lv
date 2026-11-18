from collections import OrderedDict

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser

from rag.vector_store import get_vector_store_service
from utils.prompt_loader import load_rag_prompt
from langchain_core.prompts import PromptTemplate
from model.factory import chat_model
"""
RAG总结服务类：用户提问，搜索参考资料，将提问和参考资料交给模型，模型返回总结结果
"""

def print_prompt(prompt):
    print("="*50)
    print(prompt.to_string())
    print("="*50)
    return prompt


CONTEXT_CHAR_BUDGET = 4000      # 拼进提示词的参考资料字符上限, 超过则按序截断, 防止挤爆上下文
QUERY_CACHE_SIZE = 64           # 最近 64 个 query 的检索结果缓存, 省 embedding 请求


class RagSummarizeService(object):
    def __init__(self):
        self.vector_store = get_vector_store_service()
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompt()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self.__init_chain()
        # LRU 缓存: query -> 已拼接好的 context 字符串
        self._context_cache: OrderedDict[str, str] = OrderedDict()

    def __init_chain(self):
        chain = self.prompt_template | print_prompt | self.model | StrOutputParser()
        return chain

    def _get_context(self, query: str) -> str:
        """
        检索 + 拼接参考资料, 带两层优化:
        1. LRU 缓存: 同一个 query 在 64 次内复用, 省一次 embedding 网络请求(~1s + token 费)
        2. 字符预算: 超过 CONTEXT_CHAR_BUDGET 时按序截断, 防止后续 LLM 上下文溢出
        """
        if query in self._context_cache:
            self._context_cache.move_to_end(query)
            return self._context_cache[query]

        context_docs = self.retriever.invoke(query)

        parts = []
        total = 0
        for i, doc in enumerate(context_docs, 1):
            piece = f"【参考资料{i}】:参考资料：{doc.page_content} | 参考元数据：{doc.metadata}"
            # 单块已经超预算: 整块丢弃, 避免截断一半的脏数据
            if total + len(piece) > CONTEXT_CHAR_BUDGET and total > 0:
                break
            parts.append(piece)
            total += len(piece)

        context = "\n".join(parts)

        self._context_cache[query] = context
        self._context_cache.move_to_end(query)
        if len(self._context_cache) > QUERY_CACHE_SIZE:
            self._context_cache.popitem(last=False)

        return context

    def rag_summarize(self, query: str) -> str:
        """
        RAG总结服务：用户提问，检索参考资料，将提问和参考资料交给模型，模型返回总结结果
        :param query: 用户提问
        :return: 模型总结结果
        """
        context = self._get_context(query)

        return self.chain.invoke(
            {
                "input": query,
                "context": context
            }
        )

if __name__ == '__main__':
    rag_service = RagSummarizeService()
    result = rag_service.rag_summarize("螺蛳粉为什么闻着臭吃着香")

    print(result)
