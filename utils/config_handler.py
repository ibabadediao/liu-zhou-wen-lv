
"""
配置处理类:为整个项目提供统一的配置处理
yaml格式
k: v
"""
import yaml
import os
from utils.path_tool import get_abs_path

# 加载rag.yaml配置
def load_rag_config(config_path: str=get_abs_path("config/rag.yml"),encoding: str="utf-8"):
    with open(config_path,"r",encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)   # 加载yaml文件

def load_chroma_config(config_path: str=get_abs_path("config/chroma.yml"),encoding: str="utf-8"):
    with open(config_path,"r",encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)   # 加载yaml文件

def load_prompt_config(config_path: str=get_abs_path("config/prompts.yml"),encoding: str="utf-8"):
    with open(config_path,"r",encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)   # 加载yaml文件


def load_agent_config(config_path: str=get_abs_path("config/agent.yml"),encoding: str="utf-8"):
    with open(config_path,"r",encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)   # 加载yaml文件


rag_config = load_rag_config()
chroma_config = load_chroma_config()
prompt_config = load_prompt_config()
agent_config = load_agent_config()


if __name__ == '__main__':
    print(rag_config["chat_model_name"])
