# 函数调用时序图（启动 + 单轮对话）

## 1. 启动阶段

```mermaid
sequenceDiagram
    participant U as 用户
    participant CLI as chat_cli.main
    participant ENV as _load_dotenv_file
    participant LLM as _build_llm_client
    participant MF as build_memory_stack_from_env
    participant LF as build_learning_stack

    U->>CLI: python chat_cli.py
    CLI->>ENV: 读取 .env 并填充 os.environ
    CLI->>LLM: 创建 ChatOpenAI 客户端
    CLI->>MF: 构建 MemoryStack
    MF-->>CLI: graph + vector + writer + retriever
    CLI->>LF: 构建 LearningStack
    LF-->>CLI: profile_store + knowledge_store + pipeline
    CLI-->>U: 输出“AI 助手已启动”
```

### 关键函数

1. `chat_cli.main()`
2. `chat_cli._load_dotenv_file()`
3. `chat_cli._build_llm_client()`
4. `memory.factory.build_memory_stack_from_env()`
5. `memory.learning_factory.build_learning_stack()`

## 2. 单轮普通对话阶段

```mermaid
sequenceDiagram
    participant U as 用户
    participant CLI as run_chat
    participant PS as profile_store
    participant RET as retriever.retrieve
    participant ASM as assemble_context
    participant LLM as _generate_reply_with_llm
    participant WR as writer.add_text
    participant LP as pipeline.learn_from_turn
    participant FS as fact_store(sqlite)

    U->>CLI: 输入普通文本
    CLI->>PS: list()
    PS-->>CLI: 画像事实列表
    CLI->>RET: retrieve(query)
    RET-->>CLI: RetrievalResult[]
    CLI->>ASM: assemble_context(results)
    ASM-->>CLI: 记忆上下文文本
    CLI->>LLM: invoke(system + user)
    LLM-->>CLI: assistant_text
    CLI-->>U: 输出助手回复

    CLI->>WR: add_text("用户: ...")
    CLI->>WR: add_text("助手: ...")
    WR-->>CLI: 写入记忆图与向量库

    CLI->>LP: learn_from_turn(user_msg, assistant_msg)
    LP->>FS: upsert(ProfileFact/KnowledgeFact)
    FS-->>LP: 已写入记录
    LP-->>CLI: LearningEvent
    CLI-->>U: 输出 [learn] 摘要
```

### 关键函数

1. `chat_cli.run_chat()`
2. `memory.retriever.HybridRetriever.retrieve()`
3. `memory.assembler.assemble_context()`
4. `chat_cli._generate_reply_with_llm()`
5. `memory.writer.MemoryWriter.add_text()`
6. `memory.learning.LearningPipeline.learn_from_turn()`

## 3. 单轮命令对话阶段（`/profile list` 等）

```mermaid
sequenceDiagram
    participant U as 用户
    participant CLI as run_chat
    participant CMD as handle_command
    participant FS as fact_store(sqlite)

    U->>CLI: 输入 /profile list
    CLI->>CMD: handle_command(cmd, pipeline)
    CMD->>FS: list()
    FS-->>CMD: facts
    CMD-->>CLI: 格式化文本
    CLI-->>U: 输出命令结果
```

## 4. 纠错回调阶段（`/feedback correct`）

```mermaid
sequenceDiagram
    participant U as 用户
    participant CMD as handle_command
    participant LP as feedback_correct
    participant FS as fact_store(sqlite)

    U->>CMD: /feedback correct <id> <new_value>
    CMD->>LP: feedback_correct(id, new_value)
    LP->>FS: downgrade_and_mark(old_id, factor=0.3, status=superseded)
    LP->>FS: upsert(new_fact, confidence=1.0, source=user_feedback)
    FS-->>LP: 完成
    LP-->>CMD: True
    CMD-->>U: [Feedback] ... ok
```

## 5. 代码定位索引

1. `chat_cli.py`
2. `memory/core/factory.py`
3. `memory/core/learning_factory.py`
4. `memory/retrieval/retriever.py`
5. `memory/graph/writer.py`
6. `memory/learning/pipeline.py`
7. `memory/facts/sqlite_store.py`
8. `memory/learning/commands.py`
