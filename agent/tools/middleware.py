from typing import Callable

from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call, before_model
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command
from utils.logger_handler import logger

@wrap_tool_call
def monitor_tool(
        # 请求数据封装，可以理解为参数
        request: ToolCallRequest,
        # 执行的函数（工具）本身
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:     # 工具执行的监控

    # 打印工具调用参数
    logger.info(f"[tool_monitor]执行工具:{request.tool_call['name']}")
    logger.info(f"[tool_monitor]传入参数:{request.tool_call['args']}")

    try:
        res = handler(request)   # 调用工具函数，返回结果
        logger.info(f"[tool_monitor]工具{request.tool_call['name']}调用成功")
        return res
    except Exception as e:
        logger.error(f"[tool_monitor]工具{request.tool_call['name']}调用失败，错误信息：{e}")
        raise e # 抛出异常，让调用者处理

@before_model
def log_before_model(
        state: AgentState,      # 整个Agent智能体的状态记录
        runtime: Runtime,       # 记录整个执行过程的上下文信息
):    # 模型调用前的输出日志
    logger.info(f"[log_before_model]即将调用模型，带有{len(state['messages'])}条消息")
    # 打印最后一条消息的内容
    logger.debug(f"[log_before_model]{type(state['messages'][-1]).__name__}|{state['messages'][-1].content.strip()}")
    return None
