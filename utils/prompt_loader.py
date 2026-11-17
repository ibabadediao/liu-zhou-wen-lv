from utils.config_handler import prompt_config
from utils.path_tool import get_abs_path
from utils.logger_handler import logger



def _load_prompt(path_key: str, prompt_name: str) -> str:
    """按配置键读取提示词文件的通用实现
    :param path_key: prompts.yml 中的路径配置键
    :param prompt_name: 提示词名称, 用于日志定位
    :return: 提示词文本
    """
    try:
        prompt_path = get_abs_path(prompt_config[path_key])
    except KeyError as e:
        logger.error(f"[load_prompt]在prompts.yml中缺少{path_key}配置项")
        raise e

    try:
        return open(prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_prompt]解析{prompt_name}提示词文件{prompt_path}失败: {e}")
        raise e


def load_tour_prompt():
    """文旅咨询子智能体的系统提示词"""
    return _load_prompt("tour_prompt_path", "文旅咨询")


def load_food_prompt():
    """美食推荐子智能体的系统提示词"""
    return _load_prompt("food_prompt_path", "美食推荐")


def load_itinerary_prompt():
    """行程规划子智能体的系统提示词"""
    return _load_prompt("itinerary_prompt_path", "行程规划")


def load_rag_prompt():
    """RAG检索总结提示词"""
    return _load_prompt("rag_summarize_prompt_path", "rag")


def load_router_prompt():
    """路由意图分类提示词"""
    return _load_prompt("router_prompt_path", "路由")


def load_chitchat_prompt():
    """闲聊子智能体的系统提示词"""
    return _load_prompt("chitchat_prompt_path", "闲聊")


if __name__ == "__main__":
    print(load_tour_prompt())
    print(load_food_prompt())
    print(load_itinerary_prompt())
    print(load_rag_prompt())
