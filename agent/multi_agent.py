from typing import Annotated, Any, Callable, Literal
from typing_extensions import TypedDict

from pydantic import BaseModel
from langchain.agents import create_agent
from langchain_core.messages import AnyMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from model.factory import chat_model
from utils.logger_handler import logger
from utils.prompt_loader import (load_tour_prompt, load_food_prompt,
                                 load_itinerary_prompt, load_chitchat_prompt, load_router_prompt)
from agent.tools.agent_tools import (rag_summarize, get_weather, get_user_location,
                                      get_current_date, list_documents, view_document)
from agent.tools.middleware import monitor_tool, log_before_model

# 携带的上下文记忆条数: 只取最近N条历史消息, 防止上下文过长
MAX_HISTORY_MESSAGES = 10
# 触发摘要压缩的历史条数阈值: 超过后把窗口外的旧消息滚动压缩成一条摘要
COMPRESS_THRESHOLD = 14

# 滚动摘要的压缩提示词: 强调保留事实性信息, 丢弃无信息量内容
SUMMARY_PROMPT = """你是旅行顾问的对话记录员。请把下面的对话内容压缩成要点摘要, 作为后续对话的长期记忆。
要求:
1. 必须保留事实性信息: 出行日期与天数、同行人、出发城市、预算、兴趣偏好、已推荐的景点/美食/路线、已得出的结论
2. 每条要点必须注明信息来源, 写清是"用户"说的还是"助手"说的, 例如"用户告知国庆节带父母出行3天", 严禁把用户陈述记成助手举例
3. 丢弃寒暄、重复和无信息量的内容
4. 用简洁的中文条目输出, 总长度不超过300字
5. 只输出摘要本身, 不要任何开场白或解释

{conversation}
"""


class MultiAgentState(TypedDict):
    """多智能体全局状态:
    - messages: 对话历史, 带 add_messages 注解, 各节点返回的消息会追加进列表
    - intent: 路由结果, 不带注解, 谁返回就整体覆盖
    """
    messages: Annotated[list[AnyMessage], add_messages]
    intent: str


class RouterIntent(BaseModel):
    """路由节点的结构化输出: 强制模型四选一"""
    intent: Literal["tour_qa", "food_qa", "itinerary", "chitchat"]


# ============ 路由节点: 用结构化输出做一次轻量意图分类 ============
router_llm = chat_model.with_structured_output(RouterIntent)

def router_node(state: MultiAgentState):
    last_user = state["messages"][-1].content
    try:
        result = router_llm.invoke([
            ("system", load_router_prompt()),
            ("user", last_user),
        ])
        logger.info(f"[router]意图分类结果: {result.intent}")
        return {"intent": result.intent}
    except Exception as e:
        # 解析失败兜底: chitchat Agent 不依赖外部工具, 空回答代价最小,
        # 避免把"今天心情不好"这类纯闲聊强行路由到 tour_qa 编景点
        logger.error(f"[router]意图分类失败, 兜底为 chitchat: {e}")
        return {"intent": "chitchat"}

def route_by_intent(state: MultiAgentState) -> str:
    """条件边: intent 字符串直接映射到子 Agent 节点名"""
    return state["intent"]


# ============ 四个专职子 Agent: 各自独立的工具与静态专属提示词 ============
_DOC_TOOLS = [list_documents, view_document]   # 所有子 Agent 共享的文档浏览工具

tour_agent = create_agent(
    model=chat_model,
    system_prompt=load_tour_prompt(),
    tools=[rag_summarize, get_weather, get_user_location] + _DOC_TOOLS,
    middleware=[monitor_tool, log_before_model],
)

food_agent = create_agent(
    model=chat_model,
    system_prompt=load_food_prompt(),
    tools=[rag_summarize, get_user_location] + _DOC_TOOLS,
    middleware=[monitor_tool, log_before_model],
)

itinerary_agent = create_agent(
    model=chat_model,
    system_prompt=load_itinerary_prompt(),
    tools=[rag_summarize, get_current_date, get_weather, get_user_location] + _DOC_TOOLS,
    middleware=[monitor_tool, log_before_model],
)

chitchat_agent = create_agent(
    model=chat_model,
    system_prompt=load_chitchat_prompt(),
    tools=[get_weather] + _DOC_TOOLS,
    middleware=[monitor_tool, log_before_model],
)


def _make_agent_node(agent, name: str) -> Callable:
    """把编译好的 create_agent 子图包装成 StateGraph 节点
    config: LangGraph 注入的 RunnableConfig, 必须透传给子Agent,
    否则子Agent内部的思考/工具步骤不会向上传播到父图的流式输出
    """
    def node(state: MultiAgentState, config):
        result = agent.invoke({"messages": state["messages"]}, config=config)
        return {"messages": result["messages"]}
    node.__name__ = name
    return node


def _extract_text(content: Any) -> str:
    """
    从模型流式片段中提取可展示文本:
    - 纯文本: 原样返回
    - 结构化内容块(部分模型返回 [{"type": "text", "text": "..."}]): 拼接文本块, 忽略图片等非文本块
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") in (None, "text"):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


class MultiAgentService:
    """意图路由 + 四子智能体编排:
    START -> router -> (tour_agent | food_agent | itinerary_agent | chitchat_agent) -> END
    """

    def __init__(self):
        graph = StateGraph(MultiAgentState)
        graph.add_node("router", router_node)
        graph.add_node("tour_agent", _make_agent_node(tour_agent, "tour_agent"))
        graph.add_node("food_agent", _make_agent_node(food_agent, "food_agent"))
        graph.add_node("itinerary_agent", _make_agent_node(itinerary_agent, "itinerary_agent"))
        graph.add_node("chitchat_agent", _make_agent_node(chitchat_agent, "chitchat_agent"))

        graph.add_edge(START, "router")
        graph.add_conditional_edges("router", route_by_intent, {
            "tour_qa": "tour_agent",
            "food_qa": "food_agent",
            "itinerary": "itinerary_agent",
            "chitchat": "chitchat_agent",
        })
        for name in ("tour_agent", "food_agent", "itinerary_agent", "chitchat_agent"):
            graph.add_edge(name, END)
        self.graph = graph.compile()

    def compress_history(self, history: list[dict], cache: dict | None = None):
        """
        滚动摘要压缩: 历史超过阈值时, 把"最近N条"之外的旧消息压缩成一条system摘要,
        与最近N条原文拼接返回, 用极小的token代价保住全部历史要点
        :param history: 当前会话的历史消息列表(不含本次输入)
        :param cache: 摘要缓存 {"summary": 已有摘要文本, "count": 已被摘要覆盖的消息条数}
        :return: (压缩后的消息列表, 新缓存)
        """
        cache = cache or {"summary": None, "count": 0}

        # 未超阈值: 原样返回, 不做任何压缩
        if len(history) <= COMPRESS_THRESHOLD:
            return history, cache

        split = len(history) - MAX_HISTORY_MESSAGES
        recent = history[split:]                    # 最近N条原文, 逐字保留
        new_part = history[cache["count"]:split]    # 尚未被摘要覆盖的旧消息

        # 摘要已是最新则直接复用缓存, 否则增量压缩: 旧摘要 + 新落入窗口外的消息
        if cache["summary"] and not new_part:
            summary = cache["summary"]
            logger.debug("[multi_agent]复用缓存摘要(窗口外无新增消息)")
        else:
            summary = self._summarize(cache["summary"], new_part)
            if not summary:
                # 摘要调用失败: 退回纯截断模式, 缓存保持不变, 下轮自动重试
                return recent, cache
            cache = {"summary": summary, "count": split}

        compressed = [{"role": "system",
                       "content": f"以下是本次对话此前内容的摘要：\n{summary}"}] + recent
        return compressed, cache

    def _summarize(self, prev_summary: str | None, messages: list[dict]) -> str:
        """
        调用LLM做滚动压缩: 有旧摘要时把"旧摘要+新增消息"再压一次, 否则直接压缩新增消息
        :param prev_summary: 上一次的摘要文本, None表示首次压缩
        :param messages: 需要并入摘要的消息列表
        :return: 新摘要文本, 失败返回空串
        """
        conversation = "\n".join(
            f"{'用户' if m['role'] == 'user' else '助手'}：{m['content']}" for m in messages
        )
        if prev_summary:
            conversation = f"已有摘要：\n{prev_summary}\n\n新增对话：\n{conversation}"
        try:
            response = chat_model.invoke(SUMMARY_PROMPT.format(conversation=conversation))
            summary = response.content.strip()
            logger.info(f"[multi_agent]生成滚动摘要: {summary}")
            return summary
        except Exception as e:
            logger.error(f"[multi_agent]摘要压缩失败, 本轮退回截断模式: {e}")
            return ""

    def execute_stream(self, query: str, history: list[dict] | None = None,
                       file_context: str | None = None):
        """
        执行多智能体, 支持携带历史对话实现上下文记忆
        :param query: 当前用户输入
        :param history: 当前会话的历史消息列表, 格式 [{"role": "user"/"assistant", "content": xxx}, ...]
        :param file_context: 用户上传文件解析后的文本内容, 会作为额外上下文拼进 user message
        :return: (kind, text) 二元组流
                 kind="answer"   最终回答正文
                 kind="thinking" 思考过程(模型前置规划 / 工具返回)
                 kind="demote"  修正帧: 之前误作为回答发出的文本其实是思考, 前端需收回
        """
        # 把文件上下文拼进当前 user message, 让模型在回答时能看到
        if file_context:
            query = (
                f"[用户上传的参考资料]\n{file_context}\n\n"
                f"[用户的问题]\n{query}"
            )

        # 注意: 此处绝不能再截断! 历史长度/压缩策略由compress_history统一负责,
        # 若在这里取[-N:]会把位于列表开头的摘要system消息切掉(双重截断bug)
        messages = (history or []) + [
            {"role": "user", "content": query}
        ]
        # 诊断日志: 首条为system说明摘要已随行, 若为user说明压缩未触发或被截断
        logger.info(f"[multi_agent]发送模型{len(messages)}条消息, 首条: [{messages[0]['role']}]")

        # stream_mode="messages": 逐 token 透传子Agent内部模型的生成片段
        # subgraphs=True: 否则子Agent整个节点跑完才有一次输出
        current_id = None      # 当前模型消息ID, 用于识别"换了一条消息"
        answer_buf: list[str] = []   # 当前消息已作为"回答"发出的文本
        thinking = False       # 当前消息是否已判定为"思考"(即会发起工具调用)

        for ns, (chunk, _metadata) in self.graph.stream(
            {"messages": messages}, stream_mode="messages", subgraphs=True
        ):
            # ns 为空表示事件来自父图(含 router 的结构化分类输出), 不应展示给用户
            if not ns:
                continue

            # 工具返回的是"思考素材", 归入思考过程而非最终回答
            if isinstance(chunk, ToolMessage):
                current_id = None
                thinking = False
                answer_buf = []
                text = _extract_text(chunk.content)
                if text:
                    yield ("thinking", f"\n【工具返回】{text}\n")
                continue

            text = _extract_text(chunk.content)
            msg_id = getattr(chunk, "id", None)

            # 新一条模型消息开始: 重置当前消息状态
            if msg_id != current_id:
                current_id = msg_id
                answer_buf = []
                thinking = False

            if text:
                if thinking:
                    yield ("thinking", text)
                else:
                    answer_buf.append(text)
                    yield ("answer", text)

            # 该消息发起了工具调用 => 它此前输出的文本其实是规划思考,
            # 先发 demote 让前端把这部分从回答区收回折叠区
            has_tool = bool(getattr(chunk, "tool_call_chunks", None)) or bool(
                getattr(chunk, "tool_calls", None)
            )
            if has_tool and not thinking:
                thinking = True
                if answer_buf:
                    yield ("demote", "".join(answer_buf))
                    answer_buf = []


if __name__ == '__main__':
    service = MultiAgentService()

    for question in ["柳州有哪些必去的景点", "推荐几家正宗的螺蛳粉店", "帮我规划一个柳州两日游", "今天天气怎么样"]:
        print(f"\n{'=' * 20} 用户: {question} {'=' * 20}")
        for kind, chunk in service.execute_stream(question):
            tag = {"answer": "回答", "thinking": "思考", "demote": "收回"}[kind]
            print(f"[{tag}] {chunk}", end="", flush=True)
