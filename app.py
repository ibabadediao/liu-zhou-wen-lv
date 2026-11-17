import time

import streamlit as st
from agent.multi_agent import MultiAgentService
from utils.chat_history import create_session, list_sessions, get_messages, add_message, delete_session


def render_message(role: str, content: str):
    """
    以聊天气泡样式渲染单条消息: AI回复靠左, 用户提问靠右
    :param role: 消息角色, user 或 assistant
    :param content: 消息内容
    """
    if role == "user":
        # 用户提问: 左侧留白, 气泡靠右, 头像在最右
        _, bubble, avatar = st.columns([2, 3, 0.6])
        avatar.markdown("🙋")
    else:
        # AI回复: 头像在最左, 气泡靠左, 右侧留白
        avatar, bubble, _ = st.columns([0.4, 3, 1])
        avatar.markdown("🍍")

    with bubble:
        with st.container(border=True):
            st.markdown(content)


#标题
st.title("柳州文旅智能体")
st.caption("景点咨询 · 美食推荐 · 行程规划 · 闲聊陪游")
st.divider()

# 使用session_state存储智能体实例, 确保在页面刷新后智能体实例不会被销毁
# 并在每次请求时使用相同的智能体实例
# 这样可以避免在每次请求时都创建新的智能体实例, 提高效率
if "agent" not in st.session_state:
    st.session_state["agent"] = MultiAgentService()
# 使用session_state存储用户输入的提示词, 确保在页面刷新后提示词不会被销毁
if "message" not in st.session_state:
    st.session_state["message"] = []
# 当前会话ID, 为None表示尚未落库的新对话, 首条消息发送时才真正创建会话
if "session_id" not in st.session_state:
    st.session_state["session_id"] = None
# 滚动摘要缓存: 按会话ID隔离, 记录每个会话已生成的摘要和覆盖进度, 避免重复压缩
if "summary_cache" not in st.session_state:
    st.session_state["summary_cache"] = {}


# ============ 侧边栏: 历史对话 ============
with st.sidebar:
    # 新对话按钮: 清空聊天窗口, 会话ID置为None, 等首条消息发送时才创建新会话
    if st.button("➕ 新对话", use_container_width=True):
        st.session_state["session_id"] = None
        st.session_state["message"] = []
        st.rerun()

    st.subheader("历史对话")
    for session in list_sessions():
        col_title, col_del = st.columns([5, 1])
        # 当前打开的会话高亮显示
        is_active = session["id"] == st.session_state["session_id"]
        if col_title.button(session["title"], key=f"session_{session['id']}",
                            use_container_width=True,
                            type="primary" if is_active else "secondary"):
            # 切换到历史会话: 从数据库加载消息记录
            st.session_state["session_id"] = session["id"]
            st.session_state["message"] = get_messages(session["id"])
            st.rerun()
        if col_del.button("🗑", key=f"del_{session['id']}", help="删除该会话"):
            delete_session(session["id"])
            st.session_state["summary_cache"].pop(session["id"], None)   # 同步清理摘要缓存
            # 若删除的是当前打开的会话, 同步清空聊天窗口
            if st.session_state["session_id"] == session["id"]:
                st.session_state["session_id"] = None
                st.session_state["message"] = []
            st.rerun()

    # 调试面板: 展示当前会话的上下文记忆状态, 便于观察摘要压缩是否生效及摘要内容
    with st.expander("🧠 上下文记忆状态"):
        total = len(st.session_state["message"])
        st.write(f"历史消息: **{total} 条**")
        cache = st.session_state["summary_cache"].get(st.session_state["session_id"])
        if cache and cache.get("summary"):
            st.write(f"已摘要覆盖: 前 **{cache['count']} 条** | 原文窗口: 最近 **{min(total, 10)} 条**")
            st.caption("以下摘要会以system消息形式随每轮发给模型:")
            st.text(cache["summary"])
        else:
            st.caption("摘要未启用(历史未超过14条), 模型看到全部原文")

# 加载历史信息，显示在聊天窗口中
for message in st.session_state["message"]:
    render_message(message["role"], message["content"])

#用户输入提示词
prompt = st.chat_input("问问柳州怎么玩、螺蛳粉哪家强...")

if prompt:
    # 首条消息发送时才创建会话, 避免产生没有消息的空会话
    if st.session_state["session_id"] is None:
        st.session_state["session_id"] = create_session()
    session_id = st.session_state["session_id"]

    render_message("user", prompt)   # 显示用户输入的提示词(靠右气泡)
    # 复制当前会话的历史消息(不含本次输入), 传给智能体作为上下文记忆
    history = list(st.session_state["message"])
    # 滚动摘要压缩: 超过阈值时把旧消息压成摘要(system消息), 缓存按会话隔离复用
    cache = st.session_state["summary_cache"].setdefault(session_id, {"summary": None, "count": 0})
    history, cache = st.session_state["agent"].compress_history(history, cache)
    st.session_state["summary_cache"][session_id] = cache
    st.session_state["message"].append({"role": "user", "content": prompt})  # 存储用户输入的提示词
    add_message(session_id, "user", prompt)   # 消息持久化到数据库

    response_messages = []
    # AI回复: 头像在最左, 气泡靠左
    avatar, bubble, _ = st.columns([0.6, 4, 1])
    avatar.markdown("🍍")
    with bubble:
        with st.container(border=True):
            with st.spinner("正在为您规划柳州之旅..."):
                res_stream = st.session_state["agent"].execute_stream(prompt, history)

                def capture(generator,cache_list):
                    """
                    捕获generator生成的每个chunk, 并将其存储到cache_list中
                    :param generator:
                    :param cache_list:
                    :return:
                    """

                    for chunk in generator:
                        cache_list.append(chunk)
                        for char in chunk:
                            time.sleep(0.01)
                            yield char

                st.write_stream(capture(res_stream,response_messages))  # 流式输出到AI气泡中

    # 智能体在执行过程中会生成多个chunk，意味着response_messages会存储多个chunk，
    # 我们只需要存储最后一个chunk，因为它是智能体的回复
    st.session_state["message"].append({"role": "assistant", "content": response_messages[-1]})
    add_message(session_id, "assistant", response_messages[-1])   # 消息持久化到数据库
    st.rerun()# 刷新页面, 显示最新的回复
