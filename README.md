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
conda run --no-capture-output -n langchain python demo_mamga.py
conda run --no-capture-output -n langchain python demo_learning.py
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

# 可选：打印学习候选事实调试信息（1=开启）
export MAMGA_DEBUG_CANDIDATES=1
```

### 目录结构

```text
memory/
  core/
    contracts.py
    factory.py
    learning_factory.py
  models/
    schemas.py
  graph/
    extractor.py
    store.py
    writer.py
  facts/
    store.py
    sqlite_store.py
  retrieval/
    assembler.py
    embeddings.py
    policies.py
    retriever.py
    vector_store.py
  learning/
    commands.py
    persona.py
    pipeline.py
  prompts/
    __init__.py
    chat.py
    learning.py
    graph.py
  __init__.py
demo_mamga.py
demo_learning.py
chat_cli.py
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
- 函数调用时序图（启动/对话/命令/纠错）：`docs/call-flow.md`
- 分阶段实施计划总览：`docs/phases/README.md`
- Phase A 实现文档：`docs/phases/phase-a.md`
- Phase B 实现文档：`docs/phases/phase-b.md`
- Phase C 实现文档：`docs/phases/phase-c.md`

### 解耦原则

- 业务模块（`writer/retriever`）只依赖协议接口，不依赖具体实现
- 向量后端通过适配器封装（`ChromaVectorStore` / `HashVectorStore`）
- 运行时由工厂组装（`build_memory_stack_from_env`），切换模型只改 `.env`
- Prompt 统一在 `memory/prompts/` 管理，便于后续模型切换与策略迭代

### 自学习 V1（已实现）

- 学习管道：`extract -> dedupe -> upsert`
- 存储对象：`ProfileFact`、`KnowledgeFact`
- 单用户模式：默认单实例运行（无需传用户参数）
- 持久化：默认使用 SQLite（重启不丢）
- 画像与知识抽取：LLM 结构化抽取（无关键词规则依赖）
- 纠错回调：`/feedback correct` 会将旧版本降权并标记为 `superseded`，再写入新版本
- 命令支持：
  - `/profile list`
  - `/profile history <key>`
  - `/knowledge list`
  - `/knowledge history <topic>`
  - `/profile delete <id>`
  - `/knowledge delete <id>`
  - `/feedback correct <fact_id> <new_value>`

## 完整流程

输入问题 -> 向量召回 -> 图扩展 -> 重排 -> 拼接记忆上下文 + 画像 -> 喂给 LLM -> 输出回复 -> 写回记忆 -> 学习更新画像/知识。
