from __future__ import annotations

from .pipeline import LearningPipeline


def handle_command(command: str, pipeline: LearningPipeline) -> str:
    """
    功能：解析并执行记忆/知识管理命令。
    输入：命令字符串 `command`、学习管道 `pipeline`。
    输出：可直接展示给用户的文本结果。
    """
    cmd = command.strip()
    if cmd == "/profile list":
        facts = pipeline.profile_store.list()
        if not facts:
            return "[Profile] empty"
        lines = ["[Profile]"]
        for f in facts:
            lines.append(f"- {f.id} | {f.key}={f.value} | conf={f.confidence:.2f}")
        return "\n".join(lines)

    if cmd == "/knowledge list":
        facts = pipeline.knowledge_store.list()
        if not facts:
            return "[Knowledge] empty"
        lines = ["[Knowledge]"]
        for f in facts:
            lines.append(f"- {f.id} | topic={f.topic} | conf={f.confidence:.2f} | {f.statement}")
        return "\n".join(lines)

    if cmd == "/todo list":
        facts = pipeline.task_store.list()
        if not facts:
            return "[Todo] empty"
        lines = ["[Todo]"]
        for f in facts:
            due = f" | due={f.due_date}" if f.due_date else ""
            lines.append(f"- {f.id}{due} | conf={f.confidence:.2f} | {f.content}")
        return "\n".join(lines)

    if cmd.startswith("/todo done "):
        fact_id = cmd.replace("/todo done ", "", 1).strip()
        ok = pipeline.task_store.mark_done(fact_id)
        return f"[Todo] done {fact_id}: {'ok' if ok else 'not_found'}"

    if cmd.startswith("/todo delete "):
        fact_id = cmd.replace("/todo delete ", "", 1).strip()
        ok = pipeline.task_store.delete(fact_id)
        return f"[Todo] delete {fact_id}: {'ok' if ok else 'not_found'}"

    if cmd.startswith("/profile delete "):
        fact_id = cmd.replace("/profile delete ", "", 1).strip()
        ok = pipeline.profile_store.delete(fact_id)
        return f"[Profile] delete {fact_id}: {'ok' if ok else 'not_found'}"

    if cmd.startswith("/profile history "):
        key = cmd.replace("/profile history ", "", 1).strip()
        if not key:
            return "[Profile] usage: /profile history <key>"
        facts = pipeline.profile_store.list_history(key=key)
        if not facts:
            return f"[Profile History] empty for key={key}"
        lines = [f"[Profile History] key={key}"]
        for f in facts:
            lines.append(
                f"- {f.id} | {f.key}={f.value} | conf={f.confidence:.2f} | status={f.status} | source={f.source}"
            )
        return "\n".join(lines)

    if cmd.startswith("/knowledge delete "):
        fact_id = cmd.replace("/knowledge delete ", "", 1).strip()
        ok = pipeline.knowledge_store.delete(fact_id)
        return f"[Knowledge] delete {fact_id}: {'ok' if ok else 'not_found'}"

    if cmd.startswith("/knowledge history "):
        topic = cmd.replace("/knowledge history ", "", 1).strip()
        if not topic:
            return "[Knowledge] usage: /knowledge history <topic>"
        facts = pipeline.knowledge_store.list_history(topic=topic)
        if not facts:
            return f"[Knowledge History] empty for topic={topic}"
        lines = [f"[Knowledge History] topic={topic}"]
        for f in facts:
            lines.append(
                f"- {f.id} | topic={f.topic} | conf={f.confidence:.2f} | status={f.status} | v={f.version} | {f.statement}"
            )
        return "\n".join(lines)

    if cmd.startswith("/feedback correct "):
        parts = cmd.split(" ", 3)
        if len(parts) < 4:
            return "[Feedback] usage: /feedback correct <fact_id> <new_value>"
        fact_id = parts[2].strip()
        new_value = parts[3].strip()
        ok = pipeline.feedback_correct(fact_id=fact_id, new_value=new_value)
        return f"[Feedback] correct {fact_id}: {'ok' if ok else 'not_found'}"

    return "[Command] unsupported"
