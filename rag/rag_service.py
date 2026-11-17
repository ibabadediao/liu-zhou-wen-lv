from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser

from rag.vector_store import VectorStoreService
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


class RagSummarizeService(object):
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompt()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self.__init_chain()

    def __init_chain(self):
        chain = self.prompt_template | print_prompt | self.model | StrOutputParser()
        return chain

    def rag_summarize(self, query: str) -> str:
        """
        RAG总结服务：用户提问，检索参考资料，将提问和参考资料交给模型，模型返回总结结果
        :param query: 用户提问
        :return: 模型总结结果
        """

        context_docs = self.retriever.invoke(query)

        context = ""
        counter = 0
        for dos in context_docs:
            counter += 1
            context += f"【参考资料{counter}】:参考资料：{dos.page_content} | 参考元数据：{dos.metadata}"

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