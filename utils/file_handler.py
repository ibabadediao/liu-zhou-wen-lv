import os,hashlib

from utils.logger_handler import logger
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document


def get_file_md5_hex(file_path: str):
    """"
    获取文件的MD5十六进制字符串
    :param file_path: 文件路径
    :return: 文件的MD5十六进制字符串
    """
    if not os.path.exists(file_path):     # 判断文件是否存在
        logger.error(f"[md5计算]文件{file_path}不存在")
        return

    if not os.path.isfile(file_path):    # 判断是否为文件
        logger.error(f"[md5计算]文件{file_path}不是文件")
        return

    md5_obj = hashlib.md5()
    chunk_size = 4096  # 4KB块
    try:
        with open(file_path,"rb") as f:
            while chunk := f.read(chunk_size):   # := 先赋值，再使用
                md5_obj.update(chunk)

            """
            原理：
            1. 以4KB块读取文件内容
            2. 每次读取4KB块，就更新一次md5对象
            3. 最后返回md5对象的十六进制字符串
            chunk = f.read(chunk_size)
            while chunk:
                md5_obj.update(chunk)
                chunk = f.read(chunk_size)
        
            """
            md5_hex = md5_obj.hexdigest()
            return md5_hex
    except Exception as e:
        logger.error(f"计算文件{file_path}的MD5十六进制字符串失败: {e}")
        return None



def listdir_with_allowed_type(path: str,allowed_types: tuple[str]):
    """
    列出文件目录下所有符合类型要求的文件
    :param path: 文件目录路径
    :param allowed_types: 允许的文件类型元组
    :return: 符合类型要求的文件列表
    """
    files = []

    if not os.path.isdir(path):
        logger.error(f"[listdir_with_allowed_type]文件目录{path}不是目录")
        return allowed_types

    for f in os.listdir(path):      #循环遍历文件目录下的所有文件
        if f.endswith(allowed_types):   # 如果文件类型为（.txt,.pdf等）符合允许的文件类型元组
            files.append(os.path.join(path,f))  # 加入文件列表

    return tuple(files)


def pdf_loader(file_path: str,password=None) -> list[Document]:
    return PyPDFLoader(file_path,password).load()

def text_loader(file_path: str) -> list[Document]:
    return TextLoader(file_path,encoding="utf-8").load()




