from __future__ import annotations

import argparse
import os
from datetime import date
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover - optional dependency guard
    ChatOpenAI = None  # type: ignore[assignment]

from memory import (
    MemoryWriter,
    assemble_context,
    build_learning_stack,
    build_memory_stack_from_env,
    build_persona_context,
    handle_command,
)
from memory.prompts import build_chat_system_prompt


def _load_dotenv_file(path: str = ".env") -> None:
    """
    功能：从 `.env` 文件加载环境变量（仅填充未设置项）。
    输入：`.env` 文件路径 `path`。
    输出：无，副作用是更新 `os.environ`。
    """
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # Keep CLI usable even if .env parsing fails.
        return


def parse_args() -> argparse.Namespace:
    """
    功能：解析命令行参数。
    输入：无（读取终端参数）。
    输出：解析后的参数对象。
    """
    parser = argparse.ArgumentParser(description="AI Assistant Chat CLI")
    return parser.parse_args()


def _generate_reply(user_text: str, persona_ctx: str, memory_ctx: str) -> str:
    """
    功能：生成一个轻量本地回复（无需外部 LLM）。
    输入：用户输入、画像上下文、记忆上下文。
    输出：助手回复文本。
    """
    if any(k in user_text for k in ("你是谁", "你是干嘛的", "你能做什么")):
        return (
            "我是你的定制化 AI 助手（秘书型）。"
            "我会在对话中学习你的偏好和知识，并在后续回答里持续个性化。"
        )

    if any(k in user_text for k in ("你记住了什么", "我的偏好", "画像")):
        if persona_ctx:
            return f"我当前记住的画像如下：\n{persona_ctx}"
        return "我还没有稳定画像，你可以告诉我你的偏好，比如语言、风格、时区。"

    if any(k in user_text for k in ("总结", "回顾", "检索")):
        return f"我根据当前记忆检索到如下信息：\n{memory_ctx}"

    if "时区" in user_text:
        return "收到，我会把你的时区偏好记录到长期画像中，并在后续任务时间计算时优先使用。"

    if "中文" in user_text or "简洁" in user_text:
        return "明白，我会默认中文并保持简洁回答。"

    return "我已收到，这条信息会进入学习管道并用于后续个性化回答。"


def _build_llm_client() -> Any | None:
    """
    功能：根据环境变量创建聊天模型客户端。
    输入：无（读取 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`）。
    输出：可调用的 LLM 客户端；未配置时返回 `None`。
    """
    if ChatOpenAI is None:
        return None
    api_key = os.getenv("LLM_API_KEY", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    if not api_key:
        return None
    try:
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.2,
            max_tokens=1000,
            streaming=False,
            extra_body={"reasoning_split": True},
        )
    except Exception:
        return None


def _generate_reply_with_llm(llm: Any, user_text: str, persona_ctx: str, memory_ctx: str) -> str:
    """
    功能：调用 LLM 生成回复。
    输入：LLM 客户端、用户输入、画像上下文、记忆上下文。
    输出：助手回复文本（失败时抛异常由上层兜底）。
    """
    system_text = build_chat_system_prompt(persona_ctx=persona_ctx, memory_ctx=memory_ctx)
    resp = llm.invoke(
        [
            SystemMessage(content=system_text),
            HumanMessage(content=user_text),
        ]
    )
    text = getattr(resp, "content", "")
    if isinstance(text, str):
        return text.strip() or "我暂时没有生成到有效回复，请你再说一次。"
    if isinstance(text, list):
        # Some providers may return block-style content.
        parts: list[str] = []
        for item in text:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                t = item.get("text")
                if isinstance(t, str):
                    parts.append(t)
        merged = "\n".join(p.strip() for p in parts if p and p.strip())
        return merged or "我暂时没有生成到有效回复，请你再说一次。"
    return "我暂时没有生成到有效回复，请你再说一次。"


def _format_candidate_debug(candidates: list[Any]) -> str:
    """
    功能：格式化候选事实调试输出。
    输入：候选事实对象列表。
    输出：可打印字符串。
    """
    if not candidates:
        return "[candidate] empty"
    lines = ["[candidate]"]
    for i, c in enumerate(candidates, start=1):
        if getattr(c, "fact_type", "") == "profile":
            lines.append(
                f"{i}. profile key={getattr(c, 'key', '')} value={getattr(c, 'value', '')} "
                f"conf={getattr(c, 'confidence', 0):.2f} cat={getattr(c, 'category', '')}"
            )
        else:
            if getattr(c, "fact_type", "") == "task":
                content = str(getattr(c, "content", "")).strip().replace("\n", " ")
                if len(content) > 80:
                    content = content[:80] + "..."
                lines.append(
                    f"{i}. task due={getattr(c, 'due_date', '') or '-'} conf={getattr(c, 'confidence', 0):.2f} "
                    f"cat={getattr(c, 'category', '')} content={content}"
                )
                continue
            statement = str(getattr(c, "statement", "")).strip().replace("\n", " ")
            if len(statement) > 80:
                statement = statement[:80] + "..."
            lines.append(
                f"{i}. knowledge topic={getattr(c, 'topic', '')} conf={getattr(c, 'confidence', 0):.2f} "
                f"cat={getattr(c, 'category', '')} stmt={statement}"
            )
    return "\n".join(lines)


def _build_due_task_reminder(task_facts: list[Any], reminded_ids: set[str], today: date) -> str:
    """
    功能：基于到期任务生成自动提醒文案（同会话任务仅提醒一次）。
    输入：任务列表、已提醒任务 ID 集合、当前日期 `today`。
    输出：提醒文案；无可提醒任务时返回空字符串。
    """
    due_items: list[tuple[str, str, str]] = []
    for t in task_facts:
        tid = str(getattr(t, "id", "")).strip()
        if not tid or tid in reminded_ids:
            continue
        due_raw = str(getattr(t, "due_date", "")).strip()
        if not due_raw:
            continue
        try:
            due = date.fromisoformat(due_raw[:10])
        except Exception:
            continue
        if due > today:
            continue
        content = str(getattr(t, "content", "")).strip()
        due_items.append((tid, due_raw[:10], content))

    if not due_items:
        return ""

    lines = ["提醒：以下任务已到期或今天截止："]
    for tid, due_date, content in due_items[:3]:
        lines.append(f"- [{tid}] due={due_date} | {content}")
        reminded_ids.add(tid)
    if len(due_items) > 3:
        lines.append(f"- 还有 {len(due_items) - 3} 条，请用 /todo list 查看")
    return "\n".join(lines)


def run_chat() -> None:
    """
    功能：启动终端聊天循环并在每轮自动执行记忆与学习。
    输入：无。
    输出：无，副作用是持续打印回复并写入记忆/事实库。
    """
    learning_stack = build_learning_stack()
    memory_stack: Any | None = None
    writer: MemoryWriter | None = None
    llm = _build_llm_client()
    debug_candidates = os.getenv("MAMGA_DEBUG_CANDIDATES", "0").strip() in {"1", "true", "True", "yes", "on"}
    reminded_task_ids: set[str] = set()

    def _ensure_memory_stack() -> tuple[Any, MemoryWriter]:
        nonlocal memory_stack, writer
        if memory_stack is None:
            memory_stack = build_memory_stack_from_env()
            writer = memory_stack.writer
            print("[info] 记忆检索已初始化（懒加载）。")
        return memory_stack, writer  # type: ignore[return-value]

    print("AI 助手已启动（单用户模式）。输入内容开始对话，输入 `exit` 退出。")
    print(f"回复模式：{'LLM' if llm is not None else 'Local Fallback'}")
    print(
        "可用命令：/profile list, /profile history <key>, /knowledge list, /todo list, "
        "/todo done <id>, /todo delete <id>, /feedback correct <id> <new_value>"
    )
    print()

    while True:
        try:
            user_text = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            break

        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            print("已退出。")
            break

        if user_text.startswith("/"):
            out = handle_command(user_text, pipeline=learning_stack.pipeline)
            print(f"助手: {out}\n")
            continue

        profile_facts = learning_stack.profile_store.list()
        persona_ctx = build_persona_context(profile_facts)
        try:
            current_stack, _ = _ensure_memory_stack()
            retrieved = current_stack.retriever.retrieve(query=user_text, top_k_vector=8, hops=1, top_n_final=4)
            memory_ctx = assemble_context(retrieved, max_items=4)
        except Exception as e:
            print(f"[warn] 记忆检索失败，已降级为无记忆上下文: {type(e).__name__}: {e}")
            memory_ctx = "[记忆上下文]\n(empty)"
        if llm is not None:
            try:
                assistant_text = _generate_reply_with_llm(
                    llm=llm,
                    user_text=user_text,
                    persona_ctx=persona_ctx,
                    memory_ctx=memory_ctx,
                )
            except Exception as e:
                print(f"[warn] LLM 调用失败，已回退本地兜底回复: {type(e).__name__}: {e}")
                assistant_text = _generate_reply(user_text=user_text, persona_ctx=persona_ctx, memory_ctx=memory_ctx)
        else:
            assistant_text = _generate_reply(user_text=user_text, persona_ctx=persona_ctx, memory_ctx=memory_ctx)

        reminder_text = _build_due_task_reminder(
            task_facts=learning_stack.task_store.list(),
            reminded_ids=reminded_task_ids,
            today=date.today(),
        )
        if reminder_text:
            assistant_text = f"{reminder_text}\n\n{assistant_text}"

        print(f"助手: {assistant_text}\n")

        # Write turn into memory graph for future retrieval.
        try:
            _, current_writer = _ensure_memory_stack()
            current_writer.add_text(f"用户: {user_text}", source="dialog")
            current_writer.add_text(f"助手: {assistant_text}", source="dialog")
        except Exception as e:
            print(f"[warn] 记忆写入失败，已跳过: {type(e).__name__}: {e}")

        # Learn profile/knowledge facts from this turn.
        event = learning_stack.pipeline.learn_from_turn(
            user_message=user_text,
            assistant_message=assistant_text,
        )
        print(
            f"[learn] extracted={event.extracted_count}, "
            f"profile={len(event.upserted_profile_ids)}, "
            f"knowledge={len(event.upserted_knowledge_ids)}, "
            f"tasks={len(event.upserted_task_ids)}, "
            f"reason={event.reason}\n"
        )
        if debug_candidates:
            print(_format_candidate_debug(learning_stack.pipeline.last_candidates))
            print(f"[candidate_reason] {learning_stack.pipeline.last_extract_reason}\n")

        if event.reason == "llm_parse_error":
            raw = (learning_stack.pipeline.last_extract_raw_output or "").strip()
            if len(raw) > 1000:
                raw = raw[:1000] + "...(truncated)"
            print(f"[llm_raw_output]\n{raw or '(empty)'}\n")


def main() -> None:
    """
    功能：CLI 主入口。
    输入：命令行参数。
    输出：无，副作用是运行聊天循环。
    """
    _load_dotenv_file(".env")
    parse_args()
    run_chat()


if __name__ == "__main__":
    main()
