import os

from langchain_chroma import Chroma  # 导入Chroma向量数据库
from langchain_core.documents import Document

from utils.config_handler import chroma_config
from model.factory import embedding_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.path_tool import get_abs_path
from utils.file_handler import text_loader,pdf_loader,listdir_with_allowed_type,get_file_md5_hex
from utils.logger_handler import logger


#创建向量存储服务类
class VectorStoreService:
    def __init__(self):
        # 初始化向量存储
        self.vector_store = Chroma(

            collection_name= chroma_config["collection_name"],      # 表名，用于存储向量数据
            embedding_function=embedding_model,    # 嵌入函数，使用 嵌入模型 用于将文本转换为向量表示。使用工厂模式创建嵌入模型
            persist_directory= chroma_config["persist_directory"],     # 存储目录，用于存储向量数据
        )        #
        # 初始化分割器
        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_config["chunk_size"], # 每个文本块的字符数
            chunk_overlap=chroma_config["chunk_overlap"], # 每个文本块之间的最大可重叠字符数
            separators=chroma_config["separators"],  # 文本块分隔符，用于将文本分割为多个块
            length_function=len,   # 分割函数，用于统计文本的长度
        )
        # 获取检索器对象
    def get_retriever(self):
            return self.vector_store.as_retriever(search_kwargs={'k': chroma_config["k"]})

    # ============ 知识库管理: 单文件入库 / 删除 / 查询 ============

    def _file_documents(self, path: str) -> list[Document]:
        """按扩展名读取单个知识库文件为 Document 列表"""
        if path.lower().endswith("txt"):
            return text_loader(path)
        if path.lower().endswith("pdf"):
            return pdf_loader(path)
        return []

    def _md5_path(self) -> str:
        return get_abs_path(chroma_config["md5_hex_store"])

    def _md5_exists(self, md5_hex: str) -> bool:
        md5_path = self._md5_path()
        if not os.path.exists(md5_path):
            return False
        with open(md5_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() == md5_hex:
                    return True
        return False

    def _md5_add(self, md5_hex: str):
        with open(self._md5_path(), "a", encoding="utf-8") as f:
            f.write(md5_hex + "\n")

    def _md5_remove(self, md5_hex: str):
        md5_path = self._md5_path()
        if not os.path.exists(md5_path):
            return
        with open(md5_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(md5_path, "w", encoding="utf-8") as f:
            for line in lines:
                if line.strip() != md5_hex:
                    f.write(line)

    def is_ingested(self, path: str) -> bool:
        """判断文件是否已入库(依据 md5.txt 去重清单)"""
        md5_hex = get_file_md5_hex(path)
        return bool(md5_hex) and self._md5_exists(md5_hex)

    def add_file(self, path: str) -> int:
        """切分并向量化单个知识库文件, 返回写入的文本块数(已入库/空内容返回0)"""
        md5_hex = get_file_md5_hex(path)
        if not md5_hex or self._md5_exists(md5_hex):
            return 0

        documents = self._file_documents(path)
        if not documents:
            return 0

        chunks = self.spliter.split_documents(documents)
        if not chunks:
            return 0

        self.vector_store.add_documents(chunks)
        self._md5_add(md5_hex)
        logger.info(f"[知识库管理]文件{path}已入库, 共{len(chunks)}个文本块")
        return len(chunks)

    def delete_file(self, path: str):
        """按 source 元数据删除该文件全部向量块, 并清理 md5 去重记录"""
        md5_hex = get_file_md5_hex(path)
        try:
            ids = self.vector_store.get(where={"source": path}).get("ids", [])
            if ids:
                self.vector_store.delete(ids=ids)
                logger.info(f"[知识库管理]文件{path}已删除 {len(ids)} 个向量块")
        except Exception as e:
            logger.error(f"[知识库管理]删除向量失败 {path}: {e}")
        if md5_hex:
            self._md5_remove(md5_hex)

    def reingest_file(self, path: str) -> int:
        """重新入库: 先清掉该文件已有向量与 md5 记录, 再重新切分入库"""
        self.delete_file(path)
        return self.add_file(path)

    def get_chunk_count(self, path: str) -> int:
        """统计某 source 文件在向量库中的文本块数"""
        try:
            res = self.vector_store.get(where={"source": path}, include=["metadatas"])
            return len(res.get("ids", []))
        except Exception:
            return 0

    def load_document(self):
            """
            1.从数据文件夹内读取数据文件，转为向量存入向量数据库
            2.计算文件的md5值，作为文件的唯一标识，用于判断文件是否已加载，去重
            :param self:
            :return:
            """


            def check_md5_hex(md5_for_str: str):
                # 1. 检查md5值存储文件是否存在，不存在则创建
                if not os.path.exists(get_abs_path(chroma_config["md5_hex_store"])):    #传入md5值存储文件的绝对路径
                    # 创建文件
                    open(get_abs_path(chroma_config["md5_hex_store"]), 'w', encoding='utf-8').close()
                    return False     # 文件不存在

                #2.文件存在，判断md5值是否已存在
                with open(get_abs_path(chroma_config["md5_hex_store"]), 'r', encoding='utf-8') as f:
                    for line in f.readlines(): # 读取文件每一行
                        line = line.strip()  # 移除行首行尾的所有空格
                        if line == md5_for_str:
                            return True     # md5值已存在,说明文件已处理
                    #当所有的行都遍历过后,都没有找到md5值，
                    return False     # md5值不存在,说明文件未处理过

            def save_md5_hex(md5_for_str: str):
                """
                保存md5值到文件
                :param md5_for_str: md5值
                :return:
                """
                with open(get_abs_path(chroma_config["md5_hex_store"]),'a', encoding='utf-8') as f:
                    f.write(md5_for_str+'\n')


            def get_file_document(read_path: str):
                """
                调用工具，从文件路径获取文件内容
                :param read_path: 文件路径（Document的形式）
                :return:
                """
                if read_path.endswith("txt"):
                    return text_loader(read_path)

                if read_path.endswith("pdf"):
                    return pdf_loader(read_path)


            # 1.调用工具，从数据文件夹获取被允许的文件路径   （data目录下的所有txt和pdf文件）
            allowed_files_path: list[str] = listdir_with_allowed_type(
                get_abs_path(chroma_config["data_path"]),           # 数据目录，用于存储原始文本数据
                tuple(chroma_config["allow_knowledge_file_type"])  # 允许处理的文本文件类型
            )

            # 2.遍历所有允许的文件路径
            for path in allowed_files_path:

                # 2.1获取文件的md5值
                md5_hex = get_file_md5_hex(path)
                # 2.2 检查md5是否已经处理过
                if check_md5_hex(md5_hex):
                    logger.info(f"[加载知识库]文件{path}已存在知识库，跳过")   # 文件已处理，跳过
                    continue # 跳过文件，继续处理下一个文件

                try:
                    # 3.文件未处理过，不存在知识库中，读取文件内容
                    documents: list[Document] = get_file_document(path)

                    # 检查文件内容是否为空
                    if not documents:
                        logger.info(f"[加载知识库]文件{path}内容为空，跳过")   # 文件内容为空，跳过
                        continue # 跳过文件，继续处理下一个文件

                    # 文件不存在知识库，且内容不为空，将文件内容转换为向量并存入向量数据库
                    # 1. 分割文件内容为多个文本块
                    spliter_documents: list[Document] =  self.spliter.split_documents(documents)
                    if not  spliter_documents:
                        logger.warning(f"[加载知识库]文件{path}分割后没有有效文本内容，跳过")   # 文件分割后为空，跳过
                        continue # 跳过

                    # 2.将分割后的文本块转换为向量并存入向量数据库
                    self.vector_store.add_documents(spliter_documents)

                    # 3.记录这个已经处理好文件md5值，避免下次重复加载
                    save_md5_hex(md5_hex)

                    logger.info(f"[加载知识库]文件{path}已成功加载到知识库，共{len(spliter_documents)}个文本块")

                except Exception as e:
                    # exc_info=True 用于记录详细的异常堆栈信息，如果为False，则只记录错误信息，不记录堆栈信息
                    logger.error(f"[加载知识库]文件{path}加载失败，错误信息：{str(e)}", exc_info=True)   # 加载失败，记录错误信息
                    continue # 跳过当前文件，继续处理下一个文件

# 全局唯一向量库服务实例: 供 RAG 检索与知识库管理共享,
# 保证管理员增删文档后检索即时生效(避免多个 Chroma 连接各自持有过期索引)
_vector_store_service: VectorStoreService | None = None


def get_vector_store_service() -> VectorStoreService:
    global _vector_store_service
    if _vector_store_service is None:
        _vector_store_service = VectorStoreService()
    return _vector_store_service


if __name__ == '__main__':
    vs = VectorStoreService()
    vs.load_document()  # 加载知识库
    # 2. 获取检索器对象
    retriever = vs.get_retriever()

    results =  retriever.invoke("柳州有哪些必去景点")
    for result in results:
        print(result.page_content)
        print("="*50)












