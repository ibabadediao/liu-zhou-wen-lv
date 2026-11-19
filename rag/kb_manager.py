"""
知识库管理服务: 管理员通过接口增删查知识库文档
- "文档" 即 data/ 目录下的 txt/pdf 源文件
- 新增/删除会同步维护向量库(chroma_db)与去重清单(md5.txt)
"""
import os

from rag.vector_store import get_vector_store_service
from utils.config_handler import chroma_config
from utils.path_tool import get_abs_path


class KnowledgeBaseManager:
    def __init__(self):
        # 与 RAG 检索共用同一个向量库实例, 保证增删后检索即时生效
        self.vs = get_vector_store_service()
        self.data_dir = get_abs_path(chroma_config["data_path"])
        self.allowed = tuple(chroma_config["allow_knowledge_file_type"])

    def list_documents(self) -> list[dict]:
        """列出 data/ 目录下的知识库文档及其入库状态"""
        if not os.path.isdir(self.data_dir):
            return []
        docs = []
        for f in sorted(os.listdir(self.data_dir)):
            full = os.path.join(self.data_dir, f)
            if not os.path.isfile(full):
                continue
            ext = os.path.splitext(f)[1].lower().lstrip(".")
            if ext not in self.allowed:
                continue
            ingested = self.vs.is_ingested(full)
            docs.append({
                "name": f,
                "size": os.path.getsize(full),
                "type": ext,
                "ingested": ingested,
                "chunks": self.vs.get_chunk_count(full) if ingested else 0,
            })
        return docs

    def add_document(self, filename: str, content: bytes) -> dict:
        """保存并入库一个新文档, 返回入库结果; 同名已存在或类型不支持时抛 ValueError"""
        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        if ext not in self.allowed:
            raise ValueError("仅支持 txt / pdf 格式的知识库文档")

        safe_name = os.path.basename(filename)
        dest = os.path.join(self.data_dir, safe_name)
        if os.path.exists(dest):
            raise ValueError(f"同名文档「{safe_name}」已存在, 请先删除或改名")

        with open(dest, "wb") as f:
            f.write(content)

        chunks = self.vs.add_file(dest)
        return {"name": safe_name, "ingested": chunks > 0, "chunks": chunks}

    def _resolve(self, name: str) -> str:
        """把文档名解析为 data/ 内的绝对路径, 防路径穿越; 不存在时抛 FileNotFoundError"""
        data_abs = os.path.abspath(self.data_dir)
        target = os.path.abspath(os.path.join(self.data_dir, os.path.basename(name)))
        if not target.startswith(data_abs + os.sep) or not os.path.isfile(target):
            raise FileNotFoundError(name)
        return target

    def delete_document(self, name: str) -> dict:
        """删除文档(源文件 + 向量 + 去重记录), 不存在时抛 FileNotFoundError"""
        target = self._resolve(name)
        self.vs.delete_file(target)
        os.remove(target)
        return {"deleted": os.path.basename(name)}

    def reingest_document(self, name: str) -> dict:
        """重新入库单个文档: 清掉旧向量后按当前内容重新切分入库"""
        target = self._resolve(name)
        chunks = self.vs.reingest_file(target)
        return {"name": os.path.basename(name), "ingested": chunks > 0, "chunks": chunks}

    def ingest_pending(self) -> dict:
        """批量入库 data/ 下所有尚未入库的文档"""
        pending = [d["name"] for d in self.list_documents() if not d["ingested"]]
        results = []
        for name in pending:
            chunks = self.vs.add_file(self._resolve(name))
            results.append({"name": name, "ingested": chunks > 0, "chunks": chunks})
        return {"count": len(results), "documents": results}
