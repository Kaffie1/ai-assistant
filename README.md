# ai-assistant
## MAMGA 最小可运行版本（LangChain / Conda）

这个仓库现在包含一套最小可运行的多图谱记忆架构，支持：

- 向量预召回
- 图扩展（1~2 跳）
- 简单分数融合（语义 + 图结构 + 时效 + 重要性）
- LangChain + Chroma 真实向量检索（自动降级到本地哈希向量）
- 接口解耦设计（协议 + 适配器 + 工厂），方便后续替换模型/后端

### 快速开始

```bash
conda run --no-capture-output -n langchain python chat_cli.py
conda run --no-capture-output -n langchain uvicorn web_app:app --host 0.0.0.0 --port 8000
```

运行后会看到 `Vector Mode`：
- `chroma`：使用 LangChain Embeddings + Chroma
- `hash`：依赖不可用时自动降级

Web 页面访问：`http://127.0.0.1:8000`

### 可选环境变量

```bash
# 向量提供方：huggingface（默认）或 openai
export MAMGA_EMBED_PROVIDER=huggingface

# 模型名：
# - huggingface 例子：sentence-transformers/all-MiniLM-L6-v2
# - openai 例子：text-embedding-3-small
export MAMGA_EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Chroma 数据目录（默认 ./.chroma_mamga）
export MAMGA_CHROMA_DIR=./.chroma_mamga

# 向量后端：chroma（默认）或 hash
export MAMGA_VECTOR_BACKEND=chroma

# 可选：手动指定 collection 名称（不设时会按 embedding 提供方自动隔离，避免维度冲突）
# export MAMGA_COLLECTION=mamga_memory_custom

# 自学习事实存储：sqlite（默认）或 memory
export MAMGA_FACT_STORE_BACKEND=sqlite
export MAMGA_FACT_DB_PATH=./data/facts.db

# LLM 配置（聊天与学习抽取共用）
export LLM_MODEL=gpt-4o-mini
export LLM_BASE_URL=https://api.openai.com/v1
export LLM_API_KEY=<your_api_key>

# 可选：Phase C 审计日志（JSONL）
export MAMGA_AUDIT_LOG_PATH=./data/audit.log
# 可选：短期对话缓存（JSON）
export MAMGA_RECENT_CONVERSATION_PATH=./data/recent_conversation
# 可选：Phase C 策略规则
export MAMGA_POLICY_CONFIG_PATH=./config/policy_rules.json

# 后端统一日志（文件滚动）
# 若不设置 MAMGA_LOG_PATH，会自动按启动时间生成文件名：
# 例如 ./data/logs/backend_20260415_223015.log
export MAMGA_LOG_DIR=./data/logs
# 可选：手动固定路径（设置后优先生效）
# export MAMGA_LOG_PATH=./data/backend.log
export MAMGA_LOG_LEVEL=INFO
export MAMGA_LOG_FORMAT=text   # text 或 json
export MAMGA_LOG_MAX_BYTES=5242880
export MAMGA_LOG_BACKUP_COUNT=5
export MAMGA_LOG_TO_STDOUT=1

# Web 语音输入（云端 ASR）
export MAMGA_ASR_PROVIDER=openai
export MAMGA_ASR_MODEL=gpt-4o-mini-transcribe
export MAMGA_ASR_API_KEY=<your_api_key>
export MAMGA_ASR_BASE_URL=https://api.openai.com/v1

# 运行时策略配置
export MAMGA_RUNTIME_CONFIG_PATH=./config/assistant_runtime.json
# 说明：
# - valid_statuses: history / list 类工具允许的状态过滤

# Phase C 运维参数
export MAMGA_MAINTENANCE_STALE_DAYS=30
export MAMGA_MAINTENANCE_DECAY_FACTOR=0.85
export MAMGA_MAINTENANCE_ARCHIVE_THRESHOLD=0.20
```

查看异常日志：

```bash
ls -lt ./data/logs | head
tail -f ./data/logs/backend_*.log
```

Phase C / 工具调用示例：

- `帮我看看最近的审计日志`
- `运行 dedupe 治理任务`
- `查看最近 7 天的评估摘要`
- `现在有哪些策略规则`
- `明天上午 9 点提醒我开会`
- `看看我的提醒`
- `删除 rf_xxx 这条提醒`

Web 语音输入：

- 点击输入框右侧 `语音`
- 开始说话
- 再点一次结束录音
- 识别完成后会自动把文本发送给 agent

### 目录结构

```text
core/
  contracts.py
  factory.py
  logger.py
runtime/
  command_service.py
  pending_actions.py
  tool_calling.py
  tool_registry.py
  tools/
    __init__.py
    base.py
    knowledge_tool.py
    ops_tool.py
    profile_tool.py
    remind_tool.py
    todo_tool.py
workflow/
  __init__.py
  deps.py
  graph.py
  state.py
  nodes/
    __init__.py
    fallback_reply.py
    inject_due_task_reminder.py
    load_profile_memory_context.py
    load_recent_context.py
    persist_turn.py
    retrieve_memory_context.py
    tool_call.py
prompts/
  __init__.py
  chat.py
  graph.py
  tool_router.py
speech/
  __init__.py
  asr.py
  schemas.py
entrypoints/
  __init__.py
  chat_cli.py
  web_app.py
docs/
  assistant-architecture.md
  phases/
    README.md
    phase-a.md
    phase-b.md
    phase-c.md
```

### 设计文档

- 秘书型 AI 助手架构与方案：`docs/assistant-architecture.md`
- 函数调用时序图（启动/对话/工具调用/语音输入）：`docs/call-flow.md`
- 短期记忆设计：`docs/short-term-memory-design.md`
- 分阶段实施计划总览：`docs/phases/README.md`
- Phase A 实现文档：`docs/phases/phase-a.md`
- Phase B 实现文档：`docs/phases/phase-b.md`
- Phase C 实现文档：`docs/phases/phase-c.md`
- Web 语音输入设计：`docs/asr-web-design.md`

### 解耦原则

- 业务模块（`writer/retriever`）只依赖协议接口，不依赖具体实现
- 向量后端通过适配器封装（`ChromaVectorStore` / `HashVectorStore`）
- 运行时由工厂组装（`build_memory_stack_from_env`），切换模型只改 `.env`
- Prompt 统一在 `prompts/` 管理，便于后续模型切换与策略迭代
- 工具层通过 `ToolRegistry + ToolManifest` 自动发现 `runtime/tools/*_tool.py`
- 主入口采用自然语言 `tool + args` 调用链，高风险工具要求确认
- 记忆能力统一分成三类：
  - 长期记忆：向量召回、图扩展、重排后的历史信息
  - 短期记忆：最近几轮会话上下文
  - 画像记忆：稳定偏好、习惯与画像事实
- 会话层额外维护 Recent Conversation Context：
  - 本地 JSON 缓存最近 20 条消息
  - 每次模型调用注入最近 3 轮
  - 默认路径：`./data/recent_conversation`
  - 用于补齐短期连续追问，不替代长期记忆检索
  - 提供调试/重置工具，可直接自然语言查看或清空当前短期上下文
- Web 侧支持录音 -> 云端 ASR -> 自动发送给 agent 的语音输入链路

### 自学习 V1（已实现）

- 学习管道：`extract -> dedupe -> upsert`
- 存储对象：`ProfileFact`、`KnowledgeFact`
- 单用户模式：默认单实例运行（无需传用户参数）
- 持久化：默认使用 SQLite（重启不丢）
- 画像与知识抽取：LLM 结构化抽取（无关键词规则依赖）
- 纠错回调：`/feedback correct` 会将旧版本降权并标记为 `superseded`，再写入新版本
- 工具能力支持：
  - 查看画像 / 画像历史
  - 查看知识 / 知识历史
  - 删除画像 / 删除知识
  - 对错误事实进行纠错

## 完整流程

输入问题 -> 读取画像记忆 -> 读取短期记忆 -> 检索长期记忆 -> 拼接三类记忆上下文 -> LLM 判断是否需要调用工具 -> 返回 `tool + args` -> 低风险直接执行 / 高风险进入确认 -> 工具结果回灌 LLM -> 输出最终回复 -> 写回记忆 -> 学习更新画像/知识。
