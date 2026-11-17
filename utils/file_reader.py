"""
统一文件解析器: 把用户上传的文件转成 Agent 能理解的文本内容
- 文本/Markdown/TXT: 直接读取
- PDF: pypdf 提取
- DOCX: python-docx 提取
- 图片(JPG/PNG/WEBP/GIF): 调视觉模型生成描述文本
"""
import base64
import mimetypes
import os
from pathlib import Path

from langchain_core.messages import HumanMessage
from pypdf import PdfReader

from model.factory import chat_model
from utils.logger_handler import logger
from utils.path_tool import get_abs_path

# 允许上传的扩展名
TEXT_EXTS = {".txt", ".md", ".log", ".csv", ".json", ".yaml", ".yml"}
DOCX_EXTS = {".docx"}
PDF_EXTS = {".pdf"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
ALLOWED_EXTS = TEXT_EXTS | DOCX_EXTS | PDF_EXTS | IMAGE_EXTS

# 上传目录: data/uploads/<user_id>/ 下按扩展名分类
UPLOAD_ROOT = get_abs_path("data/uploads")

# 视觉模型的看图提示词: 聚焦柳州文旅相关
IMAGE_PROMPT = (
    "请详细描述这张图片的内容。如果这是风景/景点/美食/地图/门票/行程单等与柳州旅行相关的图片，"
    "请重点提取：\n"
    "1. 图片整体内容\n"
    "2. 可见的文字信息（菜单、门票价格、路线指引等）\n"
    "3. 关键细节（景点名称、美食种类、地理位置线索等）\n"
    "如果与柳州无关，也请完整描述内容。"
)


def ensure_upload_dir(user_id: int | None = None) -> str:
    """确保上传目录存在并返回路径"""
    path = UPLOAD_ROOT if user_id is None else os.path.join(UPLOAD_ROOT, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path


def is_allowed(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTS


def save_uploaded_file(filename: str, content: bytes, user_id: int | None = None) -> tuple[str, str]:
    """
    保存上传文件到磁盘, 返回 (绝对路径, 扩展名)
    用时间戳+原始文件名避免冲突
    """
    save_dir = ensure_upload_dir(user_id)
    ext = Path(filename).suffix.lower()
    # 安全化文件名: 只保留字母数字和扩展名, 用时间戳前缀
    import time
    safe_name = f"{int(time.time() * 1000)}_{Path(filename).stem}{ext}"
    abs_path = os.path.join(save_dir, safe_name)
    with open(abs_path, "wb") as f:
        f.write(content)
    logger.info(f"[file_reader]文件已保存: {abs_path} ({len(content)} bytes)")
    return abs_path, ext


def read_text_file(path: str, max_chars: int = 30000) -> str:
    """读取纯文本文件, 截断到 max_chars 防止 token 爆炸"""
    for enc in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                text = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        text = "(无法识别文本编码)"
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... (已截断, 原文 {len(text)} 字符)"
    return text


def read_pdf(path: str, max_chars: int = 30000) -> str:
    """用 pypdf 提取 PDF 文本"""
    try:
        reader = PdfReader(path)
        pages = []
        for i, page in enumerate(reader.pages):
            try:
                pages.append(f"--- 第 {i + 1} 页 ---\n" + (page.extract_text() or ""))
            except Exception:
                pages.append(f"--- 第 {i + 1} 页 --- (提取失败)")
        text = "\n".join(pages)
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... (已截断, 原文 {len(text)} 字符)"
        return text or "(PDF 中未提取到可识别文本)"
    except Exception as e:
        logger.error(f"[file_reader]PDF 解析失败 {path}: {e}")
        return f"(PDF 解析失败: {e})"


def read_docx(path: str, max_chars: int = 30000) -> str:
    """用 python-docx 提取 Word 文档"""
    try:
        from docx import Document
        doc = Document(path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... (已截断, 原文 {len(text)} 字符)"
        return text or "(Word 文档中未提取到可识别文本)"
    except ImportError:
        logger.warning("[file_reader]python-docx 未安装, 请 pip install python-docx")
        return "(Word 文档解析需要 python-docx 依赖)"
    except Exception as e:
        logger.error(f"[file_reader]DOCX 解析失败 {path}: {e}")
        return f"(Word 文档解析失败: {e})"


def _image_to_data_url(path: str) -> str:
    """把图片文件转成 data URL 供模型调用"""
    ext = Path(path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }
    mime = mime_map.get(ext, "image/*")
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{data}"


def describe_image(path: str) -> str:
    """用主模型(deepseek-v4.1-flash 原生视觉)看图生成描述文本"""
    try:
        data_url = _image_to_data_url(path)
        msg = HumanMessage(content=[
            {"type": "text", "text": IMAGE_PROMPT},
            {"type": "image_url", "image_url": {"url": data_url}},
        ])
        resp = chat_model.invoke([msg])
        logger.info(f"[file_reader]图片描述生成成功: {os.path.basename(path)}")
        return resp.content
    except Exception as e:
        logger.error(f"[file_reader]图片理解调用失败 {path}: {e}")
        return f"(图片解析失败: {e})"


def read_file(path: str) -> tuple[str, str]:
    """
    统一入口: 根据扩展名选择解析策略
    返回 (文件类型标签, 提取到的文本内容)
    """
    ext = Path(path).suffix.lower()
    name = Path(path).name

    if ext in TEXT_EXTS:
        content = read_text_file(path)
        return "文本文件", f"📄 文件名: {name}\n\n{content}"

    if ext in PDF_EXTS:
        content = read_pdf(path)
        return "PDF 文档", f"📄 文件名: {name}\n\n{content}"

    if ext in DOCX_EXTS:
        content = read_docx(path)
        return "Word 文档", f"📄 文件名: {name}\n\n{content}"

    if ext in IMAGE_EXTS:
        desc = describe_image(path)
        return "图片", f"🖼️ 图片文件: {name}\n\n{desc}"

    return "未知类型", f"(不支持的文件扩展名: {ext})"


# ============ 工具: 列出 data/ 目录下的项目资料 ============

def list_project_documents() -> list[dict]:
    """
    列出 data/ 目录下的所有 .txt 资料文件
    供 Agent 的 view_document 工具调用
    """
    data_dir = get_abs_path("data")
    if not os.path.isdir(data_dir):
        return []
    docs = []
    for f in sorted(os.listdir(data_dir)):
        full = os.path.join(data_dir, f)
        if os.path.isfile(full) and Path(f).suffix.lower() in TEXT_EXTS:
            size = os.path.getsize(full)
            docs.append({"name": f, "size": size})
    return docs


def read_project_document(filename: str) -> str:
    """
    读取 data/ 下指定资料文件的完整内容
    防止路径穿越: 强制在 data/ 目录内
    """
    data_dir = get_abs_path("data")
    target = os.path.abspath(os.path.join(data_dir, filename))
    if not target.startswith(data_dir):
        return "(路径不合法)"
    if not os.path.isfile(target):
        return f"(文件不存在: {filename})"
    return read_text_file(target, max_chars=50000)


if __name__ == "__main__":
    # 本地自测
    print("=== 项目资料列表 ===")
    for doc in list_project_documents():
        print(f"  {doc['name']}  ({doc['size']} bytes)")

    print("\n=== 读取示例 ===")
    sample = list_project_documents()[0]["name"] if list_project_documents() else None
    if sample:
        content = read_project_document(sample)
        print(f"--- {sample} (前300字) ---")
        print(content[:300])
