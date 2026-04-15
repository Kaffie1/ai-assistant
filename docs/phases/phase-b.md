# Phase B：秘书最小可用实现文档

## 1. 阶段目标

- 实现“越聊越懂你”的自学习闭环
- 支持记忆可控（查看/删除/纠错）
- 支持持久化，保证重启不丢

## 2. 范围边界

包含：
- 用户画像与知识事实抽取写入
- 纠错回调（旧版本降权 + 新版本生效）
- 历史链查询（active/superseded）

不包含：
- 主动提醒编排引擎
- 自动质量评估面板
- 多用户权限系统

## 3. 模块与职责

1. `memory/learning.py`
- 抽取候选事实 `CandidateFact`
- 轻量去重
- 写入 `ProfileStore` / `KnowledgeStore`
- 处理纠错反馈

2. `memory/fact_store.py`
- 内存版事实存储（调试/测试）
- 支持 upsert/list/get/delete/history/downgrade

3. `memory/sqlite_fact_store.py`
- SQLite 持久化存储（默认）
- 与内存版保持同接口语义

4. `memory/commands.py`
- 命令入口：list/delete/history/feedback

5. `memory/persona.py`
- 高置信画像转 Persona Prompt 注入内容

## 4. 实现逻辑（核心流程）

### 4.1 学习流程（每轮对话）

1. 输入：`user_message + assistant_message`
2. 抽取：生成 profile/knowledge 候选
3. 去重：同轮内部去重
4. 存储层合并：依据键值或规范化文本合并
5. 写入：生成或更新事实
6. 输出：`LearningEvent`

### 4.2 纠错流程

1. 用户执行 `/feedback correct <fact_id> <new_value>`
2. 存储层先对旧事实 `downgrade_and_mark`
   - `confidence *= factor`
   - `status = superseded`
3. 插入新事实
   - `confidence = 1.0`
   - `source = user_feedback`
   - `status = active`
4. `history` 可查看版本演进

### 4.3 Persona 注入流程

1. 读取 active 且 `confidence >= threshold` 的画像事实
2. 生成固定 persona context
3. 在回答前注入系统提示

## 5. 数据结构

核心对象：
- `ProfileFact`
- `KnowledgeFact`
- `CandidateFact`
- `LearningEvent`

状态字段：
- `active`
- `superseded`
- `deleted`

## 6. 命令接口（已实现）

- `/profile list`
- `/profile history <key>`
- `/profile delete <id>`
- `/knowledge list`
- `/knowledge history <topic>`
- `/knowledge delete <id>`
- `/feedback correct <fact_id> <new_value>`

## 7. 配置与解耦

环境变量：
- `MAMGA_FACT_STORE_BACKEND=sqlite|memory`
- `MAMGA_FACT_DB_PATH=./data/facts.db`

解耦点：
- LearningPipeline 仅依赖 `ProfileStoreProtocol` / `KnowledgeStoreProtocol`
- 后续替换 PostgreSQL/Redis 仅新增适配器

## 8. 验收标准

- `demo_learning.py` 运行成功
- 可生成 profile/knowledge
- 纠错后新旧版本状态正确
- 历史查询可看到版本链
- SQLite 重启后数据可复用

## 9. 当前状态

- 核心能力已完成
- 待加强：抽取精度、冲突策略细化、自动评估指标
