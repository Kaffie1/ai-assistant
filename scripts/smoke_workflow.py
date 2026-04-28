from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from capabilities.memory.persona.context import append_persona_memory, build_persona_memory_context
from context.schemas import MemoryContext
from workflow.graph import run_assistant_graph


def _assert(condition: bool, message: str) -> None:
    """
    功能：在 smoke test 中执行断言。
    输入：断言结果 `condition`、错误信息 `message`。
    输出：无；断言失败时抛出异常。
    """
    if not condition:
        raise AssertionError(message)


def _run_normal_reply() -> None:
    """
    功能：验证普通回复链路可执行。
    输入：无。
    输出：无；断言失败时抛出异常。
    """
    state = run_assistant_graph(
        context=MemoryContext(user_text="你好，你是谁？", source="cli"),
        thread_id="smoke-normal",
    )
    _assert(bool(state.reply_text.strip()), "普通回复为空。")
    _assert(state.waiting_confirmation is False, "普通回复不应进入确认状态。")


def _run_confirm_and_cancel() -> None:
    """
    功能：验证高风险操作的确认提示与取消恢复链路。
    输入：无。
    输出：无；断言失败时抛出异常。
    """
    first = run_assistant_graph(
        context=MemoryContext(user_text="删除第三条画像", source="cli"),
        thread_id="smoke-confirm-cancel",
    )
    _assert(first.waiting_confirmation is True, "高风险操作未进入确认状态。")
    _assert("确认" in first.reply_text, "确认提示文案不正确。")

    second = run_assistant_graph(
        context=MemoryContext(user_text="取消", source="cli"),
        thread_id="smoke-confirm-cancel",
    )
    _assert(second.waiting_confirmation is False, "取消后仍处于确认状态。")
    _assert("已取消" in second.reply_text, "取消回复文案不正确。")


def _run_confirm_and_execute() -> None:
    """
    功能：验证高风险操作确认后可继续执行。
    输入：无。
    输出：无；断言失败时抛出异常。
    """
    marker = "smoke-profile-delete-marker"
    before = build_persona_memory_context()
    append_persona_memory(marker)
    first = run_assistant_graph(
        context=MemoryContext(user_text="删除第一条画像", source="cli"),
        thread_id="smoke-confirm-execute",
    )
    _assert(first.waiting_confirmation is True, "执行确认链路前未进入确认状态。")

    second = run_assistant_graph(
        context=MemoryContext(user_text="确认", source="cli"),
        thread_id="smoke-confirm-execute",
    )
    _assert(second.waiting_confirmation is False, "确认执行后仍处于确认状态。")
    _assert(bool(second.reply_text.strip()), "确认执行后的回复为空。")
    after = build_persona_memory_context()
    _assert(before != after or marker in before, "确认执行链路未产生可观察变化。")


def main() -> int:
    """
    功能：执行 workflow 最小冒烟测试。
    输入：命令行参数。
    输出：进程退出码；全部通过返回 0。
    """
    parser = argparse.ArgumentParser(description="Run workflow smoke tests.")
    parser.add_argument(
        "--mutate",
        action="store_true",
        help="额外验证确认后真实执行链路；会临时修改画像文件内容。",
    )
    args = parser.parse_args()

    _run_normal_reply()
    print("PASS normal_reply")

    _run_confirm_and_cancel()
    print("PASS confirm_and_cancel")

    if args.mutate:
        _run_confirm_and_execute()
        print("PASS confirm_and_execute")

    print("OK workflow smoke")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
