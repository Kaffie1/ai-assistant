# Phase A：基础能力实现文档

## 1. 阶段目标

- 打通多图谱记忆检索主链路
- 输出可解释检索结果
- 建立可解耦可替换的底层抽象

## 2. 范围边界

包含：
- 向量召回、图扩展、融合重排
- 记忆写入（节点 + 边）
- 向量后端与 embedding 可切换

不包含：
- 任务提醒与调度
- 长期治理任务（去重压缩定时任务）
- 用户反馈闭环

## 3. 模块与职责

1. `memory/writer.py`
- 将文本写入 `MemoryNode`
- 根据实体/主题/时间建立 `MemoryEdge`

2. `memory/vector_store.py`
- `ChromaVectorStore`：真实向量检索
- `HashVectorStore`：降级兜底
- 工厂 `create_vector_store_from_env()`

3. `memory/graph_store.py`
- 管理节点/边
- 根据 seed 节点做 hop 扩展并返回图分基础值

4. `memory/retriever.py`
- 检索三段式：向量召回 -> 图扩展 -> 重排
- 多信号融合：语义/关键词/图分/时效/重要性

5. `memory/assembler.py`
- 生成中文可解释上下文日志

## 4. 实现逻辑（核心流程）

### 4.1 写入流程

1. 输入文本
2. 抽取实体、主题、重要性（`extract_memory_payload`）
3. 生成 `MemoryNode` 并写入图存储
4. 写入向量存储
5. 建立实体/语义/时间边

### 4.2 检索流程

1. 向量召回：拿 top-k 候选
2. 图扩展：以高相关 seed 做 1~2 hop 扩展
3. 重排：融合多分数并过滤低相关候选
4. 输出：Top-N + 可解释原因

### 4.3 重排策略

`final = a*semantic + b*lexical + c*graph + d*recency + e*importance`

增强策略：
- 对弱语义节点的图分做门控
- 对零关键词重合且语义偏弱的候选施加惩罚

## 5. 配置与解耦

环境变量：
- `MAMGA_EMBED_PROVIDER`
- `MAMGA_EMBED_MODEL`
- `MAMGA_VECTOR_BACKEND`
- `MAMGA_CHROMA_DIR`

解耦原则：
- 业务层依赖 `Protocol`，不依赖具体第三方 SDK
- 后端替换只改适配器/工厂，不改检索主流程

## 6. 接口与入口

- `build_memory_stack_from_env()`：统一装配入口
- `demo_mamga.py`：阶段验收脚本

## 7. 验收标准

- demo 可运行并返回可解释结果
- 可在 `.env` 切换 embedding/provider/backend
- 当依赖不可用时可自动降级到 hash 检索

## 8. 当前状态

- 已完成并可运行
