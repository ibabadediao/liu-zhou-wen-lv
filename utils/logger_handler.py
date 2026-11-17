from datetime import datetime
import logging
from utils.path_tool import get_abs_path
import os

# 日志保存的根目录
LOG_ROOT = get_abs_path('logs')

# 确保日志的目录存在
os.makedirs(LOG_ROOT, exist_ok=True)

# 日志的格式配置  error info debug
DEFAULT_LOG_FORMAT= logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)

# 获取日志记录器
def get_logger(
        name: str = "agent",
        console_level:int = logging.INFO,
        file_level:int = logging.DEBUG,
        log_file = None
) ->logging.Logger:
    logger = logging.getLogger(name)  # 创建日志记录器
    logger.setLevel(logging.DEBUG)    # 日志级别设置为调试级别

    # 避免重复添加处理器
    if logger.handlers:
        return logger


    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)   #
    console_handler.setFormatter(DEFAULT_LOG_FORMAT)

    logger.addHandler(console_handler)

    # 创建文件处理器
    if not log_file:          # 日志文件的存放路径
        log_file = os.path.join(LOG_ROOT, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    file_handler = logging.FileHandler(log_file,encoding='utf-8')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(DEFAULT_LOG_FORMAT)

    logger.addHandler(file_handler)

    return logger

logger = get_logger()


if __name__ == '__main__':
    logger.info('这是一条信息日志')
    logger.debug('这是一条调试日志')
    logger.error('这是一条错误日志')
    logger.warning('这是一条警告日志')