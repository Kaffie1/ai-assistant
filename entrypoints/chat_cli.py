from __future__ import annotations

import argparse

from capabilities.memory.store.core import build_fact_store_stack
from gateway import CliGateway
from foundation.logger import get_backend_logger, setup_backend_logging
from runtime import AppRuntime, ToolRuntime
from workflow import configure_assistant_runtime


def parse_args() -> argparse.Namespace:
    """
    功能：解析命令行参数。
    输入：无（读取终端参数）。
    输出：解析后的参数对象。
    """
    parser = argparse.ArgumentParser(description="AI Assistant Chat CLI")
    return parser.parse_args()


def run_chat() -> None:
    """
    功能：启动终端聊天循环并在每轮自动执行记忆与学习。
    输入：无。
    输出：无，副作用是持续打印回复并写入记忆/事实库。
    """
    fact_store_stack = build_fact_store_stack()
    runtime = AppRuntime(
        logger_name="chat_cli",
        fact_store_stack=fact_store_stack,
    )
    tool_runtime = ToolRuntime()
    configure_assistant_runtime(source="cli", app_runtime=runtime, tool_runtime=tool_runtime)
    gateway = CliGateway()

    print("AI 助手已启动（单用户模式）。输入内容开始对话，输入 `exit` 退出。")
    print(f"回复模式：{'LLM' if runtime.llm is not None else 'Local Fallback'}")
    print("当前为自然语言工具调用模式。直接描述你的需求即可；高风险操作会要求你确认。")
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

        result = gateway.process_chat(user_text)
        print(f"助手: {result.reply}\n")


def main() -> None:
    """
    功能：CLI 主入口。
    输入：命令行参数。
    输出：无，副作用是运行聊天循环。
    """
    setup_backend_logging()
    logger = get_backend_logger("chat_cli")
    logger.info("cli start")
    parse_args()
    try:
        run_chat()
    except Exception:
        logger.exception("cli fatal error")
        raise


if __name__ == "__main__":
    main()
