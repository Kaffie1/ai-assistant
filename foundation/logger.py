from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

from foundation.config import (
    MAMGA_LOG_BACKUP_COUNT,
    MAMGA_LOG_DIR,
    MAMGA_LOG_FORMAT,
    MAMGA_LOG_LEVEL,
    MAMGA_LOG_MAX_BYTES,
    MAMGA_LOG_PATH,
    MAMGA_LOG_TO_STDOUT,
)
from foundation.time_utils import iso_now_beijing

class _JsonFormatter(logging.Formatter):
    """
    功能：将日志格式化为 JSON 行，便于后端排错与检索。
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": iso_now_beijing(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            payload["request_id"] = getattr(record, "request_id")
        if hasattr(record, "path"):
            payload["path"] = getattr(record, "path")
        if hasattr(record, "method"):
            payload["method"] = getattr(record, "method")
        if hasattr(record, "status_code"):
            payload["status_code"] = getattr(record, "status_code")
        if hasattr(record, "duration_ms"):
            payload["duration_ms"] = getattr(record, "duration_ms")
        return json.dumps(payload, ensure_ascii=False)


class _TextFormatter(logging.Formatter):
    """
    功能：文本日志格式器，附加常用排错字段。
    """

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras: list[str] = []
        for key in ("request_id", "method", "path", "status_code", "duration_ms"):
            if hasattr(record, key):
                value = getattr(record, key)
                if value is None:
                    continue
                if key == "duration_ms":
                    try:
                        extras.append(f"{key}={float(value):.2f}")
                        continue
                    except Exception:
                        pass
                extras.append(f"{key}={value}")
        if extras:
            return f"{base} | " + " | ".join(extras)
        return base


def _log_level_from_env() -> int:
    return getattr(logging, MAMGA_LOG_LEVEL, logging.INFO)


def _log_formatter() -> logging.Formatter:
    if MAMGA_LOG_FORMAT == "json":
        return _JsonFormatter()
    return _TextFormatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _default_log_path() -> str:
    """
    功能：生成按创建时间命名的日志文件路径。
    输入：无。
    输出：形如 `./data/logs/backend_YYYYMMDD_HHMMSS.log` 的路径。
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(MAMGA_LOG_DIR, f"backend_{stamp}.log")


def setup_backend_logging() -> logging.Logger:
    """
    功能：初始化后端统一日志系统（文件滚动 + 可选控制台）。
    输入：无。
    输出：根日志器 `mamga`。
    """
    logger = logging.getLogger("mamga")
    if logger.handlers:
        return logger

    logger.setLevel(_log_level_from_env())
    formatter = _log_formatter()

    log_path = MAMGA_LOG_PATH or _default_log_path()
    max_bytes = MAMGA_LOG_MAX_BYTES
    backup_count = MAMGA_LOG_BACKUP_COUNT

    parent = os.path.dirname(log_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    file_handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if MAMGA_LOG_TO_STDOUT:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    logger.propagate = False
    logger.info(
        "backend logging ready",
        extra={
            "path": log_path,
            "method": "setup",
            "status_code": 0,
            "duration_ms": 0.0,
        },
    )
    return logger


def get_backend_logger(name: str) -> logging.Logger:
    """
    功能：获取业务子日志器（自动确保根日志已初始化）。
    输入：子模块名 `name`。
    输出：子日志器对象。
    """
    setup_backend_logging()
    return logging.getLogger(f"mamga.{name}")
