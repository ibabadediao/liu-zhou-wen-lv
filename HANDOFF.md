# 柳州文旅智能体 · 项目交接文档

> 更新日期：2026-10-26
> 项目路径：`E:\学习资料\AI柳州文旅Agent`
> 源项目（参考）：`e:\学习资料\AI大模型RAG智能体开发_Agent`（扫地机器人智能客服，gitee: wei-shengyou/agent-sweep-bot）
> 领域资料：`E:\学习资料\柳州agent项目资料`（24 个 txt 已复制到本项目 `data\`；另有 `参考资料_PDF\` 4 个政府规划 PDF 未入库）

---

## 一、项目目标

把"扫地机器人智能客服"多智能体项目改造为【柳州文旅智能体】：
- 主入口：FastAPI 独立 Web 服务（`POST /chat`，SSE 流式）
- 调试界面：保留 Streamlit（`app.py`）
- 4 个子智能体：文旅咨询 / 美食推荐 / 行程规划 / 闲聊（用户已确认此划分）

## 二、当前状态：代码改造已全部完成，静态验证通过

**架构**：`START → router(意图4分类) → (tour_agent | food_agent | itinerary_agent | chitchat_agent) → END`

### 文件清单与改造要点

| 文件 | 状态 | 说明 |
|---|---|---|
| `prompts/router_prompt.txt` | 重写 | 4 类意图：tour_qa / food_qa / itinerary / chitchat，兜底 tour_qa |
| `prompts/tour_prompt.txt` | 新建 | 文旅咨询 ReAct 提示词（rag_summarize / get_weather / get_user_location） |
| `prompts/food_prompt.txt` | 新建 | 美食推荐（rag_summarize / get_user_location） |
| `prompts/itinerary_prompt.txt` | 新建 | 行程规划（rag_summarize / get_current_date / get_weather / get_user_location），输出 Markdown 行程表 |
| `prompts/chitchat_prompt.txt` | 重写 | "柳州文旅小助"闲聊（get_weather） |
| `prompts/rag_summarize_prompt.txt` | 未改 | 本就通用（基于参考资料总结） |
| `config/prompts.yml` | 重写 | 指向上述 6 个提示词 |
| `agent/multi_agent.py` | 重写 | 4 子智能体编排；SUMMARY_PROMPT 改为旅行对话记录员（保留出行日期/天数/同行人/偏好）；compress_history 逻辑不变 |
| `agent/tools/agent_tools.py` | 重写 | 删除扫地机器人 Mock（get_user_id/get_current_month/fetch_external_data/external_data）；新增 `get_current_date`；高德密钥读环境变量 `AMAP_API_KEY`/`AMAP_PRIVATE_KEY`，yaml 为空兜底 |
| `utils/prompt_loader.py` | 重写 | `load_tour_prompt/load_food_prompt/load_itinerary_prompt/load_router_prompt/load_chitchat_prompt/load_rag_prompt`（通用 `_load_prompt` 实现） |
| `main.py` | 新建 | FastAPI 入口：`POST /chat` SSE（事件：session→chunk*→end）、`GET /health`、会话列表/消息/删除；全局单例 MultiAgentService；summary_caches 按会话隔离 |
| `app.py` | 改造 | 标题/文案改柳州文旅主题，逻辑不变 |
| `config/chroma.yml` | 改 | collection_name=`liuzhou_tourism`，chunk 400/overlap 50，k=4 |
| `config/agent.yml` | 改 | 高德 key 已清空（走环境变量）；保留 chat_db_path |
| `config/rag.yml` | 未改 | qwen3-max + text-embedding-v4 |
| `tests/test_compress.py` | 改 | 改为 import MultiAgentService（原引用遗留 react_agent） |
| `requirements.txt` | 新建 | streamlit/fastapi/uvicorn/langchain 全家桶/langgraph/dashscope/pypdf/pytest 等 |
| `data\` | 24 个 txt | 01_城市概况 ~ 24_文化，与源资料逐字一致 |
| 已删除 | — | `agent/react_agent.py`（遗留坏代码）、`prompts/main_prompt.txt`、`prompts/report_prompt.txt` |

**验证结果**：9 个 py 文件 AST 语法通过；4 个 YAML 可解析；6 个提示词文件齐套；data 下 24 个 txt 在位；全项目无"扫地机器人/客服/旧 Mock 工具"残留引用。

## 三、待办：需在本机终端执行（代码无待办）

```powershell
cd E:\学习资料\AI柳州文旅Agent
pip install -r requirements.txt

# 1. 重建知识库（24 txt 向量化，必须先做，需 DASHSCOPE_API_KEY）
python rag/vector_store.py

# 2. 启动 FastAPI（主入口）
uvicorn main:app --port 8000

# 3. 冒烟测试（SSE 流）
curl -N -X POST localhost:8000/chat -H "Content-Type: application/json" -d "{\"query\":\"柳州两日游怎么安排\"}"

# 或：Streamlit 调试界面
streamlit run app.py

# 单元测试（不消耗 API 额度）
pytest tests/test_compress.py -v
```

环境变量：
- `DASHSCOPE_API_KEY`：必设（ChatTongyi + DashScopeEmbeddings），沿用原项目环境配置即可
- `AMAP_API_KEY` / `AMAP_PRIVATE_KEY`：可选，不设只影响 IP 定位工具，其余功能正常（高德控制台"Web服务"类型 key + 数字签名私钥）

可选扩展：4 个政府规划 PDF 想入库，直接拷进 `data\` 重跑 `python rag/vector_store.py`（md5.txt 自动去重）。

## 四、关键技术约定与坑（改代码前必读）

1. **execute_stream 绝不能再截断历史**：截断/压缩统一由 `compress_history` 负责；若在 execute_stream 里再取 `[-N:]` 会把开头的摘要 system 消息切掉（双重截断 bug，`tests/test_compress.py::test_execute_stream_keeps_summary_message` 是回归测试）。
2. **SSE chunk 语义**：`execute_stream` yield 的是"子智能体内部各超级步的最后一条消息"（AI思考 / 工具结果 / 最终回答各一条），**不是增量 delta**；最终完整回答 = 最后一个 chunk。main.py 的 end 事件、app.py 的 `response_messages[-1]` 都依赖这一点。
3. **摘要缓存按会话隔离**：FastAPI 用模块级 `summary_caches` 字典（进程重启丢失无碍，最多多做一次压缩）；Streamlit 用 session_state。换会话必须换 cache。
4. **向量库去重**：靠 `md5.txt` 记录已处理文件；若清空/更换 `collection_name` 或改了切分参数想重灌，需删掉 `chroma_db\` 和 `md5.txt` 再跑 ingest。
5. **意图兜底**：router 结构化输出解析失败时兜底 `tour_qa`（文旅咨询占大头，兜错损失最小）。
6. **子图流式**：`graph.stream(..., subgraphs=True)` 且 config 必须透传给子 Agent，否则前端看不到思考/工具过程。

## 五、验收样例（4 条意图各一条）

| 意图 | 测试问题 |
|---|---|
| tour_qa | 柳州有哪些必去的景点 |
| food_qa | 推荐几家正宗的螺蛳粉店 |
| itinerary | 帮我规划一个柳州两日游 |
| chitchat | 今天天气怎么样 |

对照日志确认：router 打出 `[router]意图分类结果: xxx`，命中对应子智能体，RAG 类问题能检索到 `data\` 资料内容。
