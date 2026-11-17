"""
compress_history 滚动摘要压缩的单元测试
运行: pytest tests/test_compress.py -v
说明: 全部用例 stub 掉 _summarize, 不产生任何 API 调用费用
"""
import pytest

from agent.multi_agent import MultiAgentService, COMPRESS_THRESHOLD, MAX_HISTORY_MESSAGES


@pytest.fixture
def agent():
    """跳过__init__构造真实agent, 只测compress_history的纯逻辑"""
    agent = MultiAgentService.__new__(MultiAgentService)
    agent.calls = []

    def fake_summarize(prev, msgs):
        agent.calls.append((bool(prev), len(msgs)))
        return f"摘要#{len(agent.calls)}(前摘要={'有' if prev else '无'},新增{len(msgs)}条)"

    agent._summarize = fake_summarize
    return agent


def msg(i, role="user"):
    return {"role": role, "content": f"消息{i}"}


def test_below_threshold_untouched(agent):
    """未超阈值: 原样返回, 不触发摘要调用"""
    history = [msg(i) for i in range(COMPRESS_THRESHOLD)]
    out, cache = agent.compress_history(history)
    assert out is history
    assert cache == {"summary": None, "count": 0}
    assert agent.calls == []


def test_first_compression(agent):
    """首次超阈值: 旧消息压成system摘要 + 最近N条原文"""
    history = [msg(i) for i in range(COMPRESS_THRESHOLD + 1)]   # 15条
    out, cache = agent.compress_history(history)
    assert len(out) == MAX_HISTORY_MESSAGES + 1
    assert out[0]["role"] == "system" and "摘要#1" in out[0]["content"]
    assert out[1:] == history[-MAX_HISTORY_MESSAGES:]
    assert cache["count"] == len(history) - MAX_HISTORY_MESSAGES
    assert agent.calls == [(False, 5)]


def test_cache_reuse_no_regrow(agent):
    """历史无新增: 直接复用缓存摘要, 不再调用LLM"""
    history = [msg(i) for i in range(COMPRESS_THRESHOLD + 1)]
    _, cache = agent.compress_history(history)
    n_calls = len(agent.calls)
    agent.compress_history(history, cache)
    assert len(agent.calls) == n_calls   # 没有新调用


def test_incremental_summarize(agent):
    """历史增长: 只把新落窗的消息并入旧摘要, 增量调用一次"""
    history = [msg(i) for i in range(COMPRESS_THRESHOLD + 1)]
    _, cache = agent.compress_history(history)
    grown = history + [msg(99, "assistant"), msg(100)]
    out, cache = agent.compress_history(grown, cache)
    assert agent.calls[-1] == (True, 2)          # 带旧摘要 + 2条新增
    assert len(out) == MAX_HISTORY_MESSAGES + 1
    assert out[1:] == grown[-MAX_HISTORY_MESSAGES:]
    assert cache["count"] == len(grown) - MAX_HISTORY_MESSAGES


def test_fallback_to_truncation_on_failure(agent):
    """摘要调用失败: 退回纯截断(无system消息), 缓存保持不变以便下轮重试"""
    history = [msg(i) for i in range(COMPRESS_THRESHOLD + 1)]
    _, cache = agent.compress_history(history)
    grown = history + [msg(99, "assistant"), msg(100)]   # 新增消息→有新内容待摘要
    agent._summarize = lambda prev, msgs: ""
    out, cache2 = agent.compress_history(grown, cache)
    assert out == grown[-MAX_HISTORY_MESSAGES:]
    assert cache2 == cache


def test_execute_stream_keeps_summary_message(agent):
    """回归测试: execute_stream不得再截断, 否则会把开头的摘要system消息切掉(双重截断bug)"""
    captured = {}

    class FakeGraph:
        def stream(self, input_dict, **kwargs):
            captured.update(input_dict)
            return iter([])   # 不产生chunk, 只捕获入参

    agent.graph = FakeGraph()
    history = [{"role": "system", "content": "对话摘要"}, *(
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(10)
    )]
    list(agent.execute_stream("问题", history))
    sent = captured["messages"]
    assert sent[0]["role"] == "system" and sent[0]["content"] == "对话摘要"   # 摘要必须完好
    assert sent[-1] == {"role": "user", "content": "问题"}                    # 本次输入在末尾
    assert len(sent) == 12                                                    # 摘要10条历史+新输入, 一条不少


@pytest.mark.skip(reason="集成测试: 消耗真实API额度, 需要时手动去掉skip运行")
def test_real_llm_summary():
    """真实LLM压缩一次, 肉眼检查摘要质量"""
    service = MultiAgentService()
    history = [{"role": "user" if i % 2 == 0 else "assistant",
                "content": f"第{i}轮: 我计划五一从广州去柳州玩3天, 带父母, 想看紫荆花和夜游柳江"} for i in range(15)]
    out, _ = service.compress_history(history)
    assert out[0]["role"] == "system" and "紫荆花" in out[0]["content"]
    print("\n摘要内容:", out[0]["content"])
