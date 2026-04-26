from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from .tools.base import ToolContext, ToolManifest, ToolRegistry

_TOOLS_PACKAGE = "runtime.tools"
_TOOLS_DIR = Path(__file__).with_name("tools")


@dataclass(slots=True)
class _RegistrySnapshot:
    """记录工具文件快照，用于判断是否需要热刷新。"""
    files: dict[str, int]


def _iter_tool_module_names() -> list[str]:
    """
    功能：扫描 tools 目录下可自动注册的工具模块。
    输入：无。
    输出：模块全名列表，仅包含 `*_tool.py` 文件。
    """
    importlib.invalidate_caches()
    names: list[str] = []
    for module_info in pkgutil.iter_modules([str(_TOOLS_DIR)]):
        if module_info.ispkg:
            continue
        if not module_info.name.endswith("_tool"):
            continue
        names.append(f"{_TOOLS_PACKAGE}.{module_info.name}")
    names.sort()
    return names


def _build_snapshot(module_names: list[str]) -> _RegistrySnapshot:
    """
    功能：记录当前工具目录的文件修改时间，用于热刷新判断。
    输入：工具模块全名列表。
    输出：快照对象。
    """
    files: dict[str, int] = {}
    for module_name in module_names:
        short_name = module_name.rsplit(".", 1)[-1]
        file_path = _TOOLS_DIR / f"{short_name}.py"
        try:
            files[str(file_path)] = file_path.stat().st_mtime_ns
        except FileNotFoundError:
            files[str(file_path)] = -1
    return _RegistrySnapshot(files=files)


def _load_tool_module(module_name: str) -> ModuleType | None:
    """
    功能：导入或热重载单个工具模块。
    输入：模块全名 `module_name`。
    输出：模块对象；失败时返回 `None`。
    """
    try:
        module = importlib.import_module(module_name)
        return importlib.reload(module)
    except Exception:
        return None


def _manifest_dicts(module: ModuleType) -> list[dict[str, ToolManifest]]:
    """
    功能：从工具模块中提取 manifest 字典。
    输入：工具模块对象。
    输出：符合结构的 manifest 字典列表。
    """
    out: list[dict[str, ToolManifest]] = []
    for value in vars(module).values():
        if not isinstance(value, dict) or not value:
            continue
        if all(isinstance(k, str) and isinstance(v, ToolManifest) for k, v in value.items()):
            out.append(value)
    return out


def _register_module_tools(registry: ToolRegistry, module: ModuleType) -> None:
    """
    功能：根据 manifest 自动把工具模块中的 handler 注册进 registry。
    输入：工具注册表 `registry` 与模块对象 `module`。
    输出：无，副作用是注册工具。
    """
    for manifest_map in _manifest_dicts(module):
        for fallback_name, manifest in manifest_map.items():
            action = (manifest.action or fallback_name).strip()
            if not action:
                continue
            handler_name = f"handle_{action}"
            handler = getattr(module, handler_name, None)
            if callable(handler):
                registry.register(action, handler, manifest)


class AutoReloadToolRegistry:
    """
    功能：维护一个支持目录扫描和热刷新的工具注册表。
    输入：无。
    输出：可按需返回最新的 `ToolRegistry`。
    """

    def __init__(self) -> None:
        """
        功能：初始化支持热刷新的工具注册器。
        输入：无。
        输出：无，建立初始空 registry 与快照。
        """
        self._registry = ToolRegistry()
        self._snapshot = _RegistrySnapshot(files={})

    def _refresh_if_needed(self) -> None:
        """
        功能：在工具文件发生变化时重建工具注册表。
        输入：无。
        输出：无，副作用是刷新内部 registry。
        """
        module_names = _iter_tool_module_names()
        snapshot = _build_snapshot(module_names)
        if snapshot.files == self._snapshot.files and self._registry.list_names():
            return

        registry = ToolRegistry()
        for module_name in module_names:
            module = _load_tool_module(module_name)
            if module is None:
                continue
            _register_module_tools(registry, module)
        self._registry = registry
        self._snapshot = snapshot

    def get_registry(self) -> ToolRegistry:
        """
        功能：返回已自动刷新的最新工具注册表。
        输入：无。
        输出：`ToolRegistry` 实例。
        """
        self._refresh_if_needed()
        return self._registry


_AUTO_REGISTRY = AutoReloadToolRegistry()


def build_default_tool_registry() -> ToolRegistry:
    """
    功能：兼容旧调用方式，返回自动刷新的工具注册表。
    输入：无。
    输出：`ToolRegistry` 实例。
    """
    return _AUTO_REGISTRY.get_registry()
