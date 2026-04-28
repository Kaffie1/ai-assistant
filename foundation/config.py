from __future__ import annotations

import os
from pathlib import Path


def load_dotenv_file(path: str = ".env") -> None:
    """
    功能：读取本地 `.env` 文件，并仅补充当前进程中尚未设置的环境变量。
    输入：`.env` 文件路径 `path`。
    输出：无，副作用是写入 `os.environ`。
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
        return


def _env_str(name: str, default: str = "") -> str:
    """
    功能：读取字符串环境变量并去掉首尾空白。
    输入：环境变量名 `name` 与默认值 `default`。
    输出：字符串结果。
    """
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    """
    功能：读取整型环境变量。
    输入：环境变量名 `name` 与默认值 `default`。
    输出：整型结果；异常时回退默认值。
    """
    try:
        return int(_env_str(name, str(default)) or default)
    except Exception:
        return default


def _env_bool(name: str, default: bool) -> bool:
    """
    功能：读取布尔环境变量。
    输入：环境变量名 `name` 与默认值 `default`。
    输出：布尔结果。
    """
    return _env_str(name, str(int(default))).lower() in {"1", "true", "yes", "on"}


load_dotenv_file(".env")


# LLM
LLM_API_KEY = _env_str("LLM_API_KEY")
LLM_BASE_URL = _env_str("LLM_BASE_URL")
LLM_MODEL = _env_str("LLM_MODEL", "gpt-4o-mini") or "gpt-4o-mini"

# ASR
MAMGA_ASR_PROVIDER = _env_str("MAMGA_ASR_PROVIDER", "openai") or "openai"
MAMGA_ASR_MODEL = _env_str("MAMGA_ASR_MODEL", "gpt-4o-mini-transcribe") or "gpt-4o-mini-transcribe"
MAMGA_ASR_API_KEY = _env_str("MAMGA_ASR_API_KEY") or LLM_API_KEY
MAMGA_ASR_BASE_URL = _env_str("MAMGA_ASR_BASE_URL") or LLM_BASE_URL or "https://api.openai.com/v1"

# Embedding / vector
MAMGA_EMBED_PROVIDER = _env_str("MAMGA_EMBED_PROVIDER", "huggingface").lower() or "huggingface"
MAMGA_EMBED_MODEL = _env_str("MAMGA_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2") or "sentence-transformers/all-MiniLM-L6-v2"
MAMGA_VECTOR_BACKEND = _env_str("MAMGA_VECTOR_BACKEND", "chroma").lower() or "chroma"
MAMGA_COLLECTION = _env_str("MAMGA_COLLECTION")
MAMGA_CHROMA_DIR = _env_str("MAMGA_CHROMA_DIR", "./.chroma_mamga") or "./.chroma_mamga"

# Fact store
MAMGA_FACT_STORE_BACKEND = _env_str("MAMGA_FACT_STORE_BACKEND", "sqlite").lower() or "sqlite"
MAMGA_FACT_DB_PATH = _env_str("MAMGA_FACT_DB_PATH", "./data/facts.db") or "./data/facts.db"

# Runtime
MAMGA_RECENT_CONVERSATION_PATH = _env_str("MAMGA_RECENT_CONVERSATION_PATH", "./data/recent_conversation") or "./data/recent_conversation"
MAMGA_PROFILE_MEMORY_PATH = _env_str("MAMGA_PROFILE_MEMORY_PATH", "./data/profile_memory.json") or "./data/profile_memory.json"
MAMGA_LONG_TERM_MEMORY_DB_PATH = _env_str("MAMGA_LONG_TERM_MEMORY_DB_PATH", "./data/long_term_memory.db") or "./data/long_term_memory.db"
MAMGA_LONG_TERM_MEMORY_RULES_PATH = _env_str("MAMGA_LONG_TERM_MEMORY_RULES_PATH", "./data/long_term_memory_rules.json") or "./data/long_term_memory_rules.json"
MAMGA_TASK_MEMORY_MD_PATH = _env_str("MAMGA_TASK_MEMORY_MD_PATH", "./data/task_memory.md") or "./data/task_memory.md"
MAMGA_REMINDER_MEMORY_MD_PATH = _env_str("MAMGA_REMINDER_MEMORY_MD_PATH", "./data/reminder_memory.md") or "./data/reminder_memory.md"

# Paths
MAMGA_LOG_DIR = _env_str("MAMGA_LOG_DIR", "./data/logs") or "./data/logs"
MAMGA_LOG_PATH = _env_str("MAMGA_LOG_PATH")

# Logging
MAMGA_LOG_LEVEL = _env_str("MAMGA_LOG_LEVEL", "INFO").upper() or "INFO"
MAMGA_LOG_FORMAT = _env_str("MAMGA_LOG_FORMAT", "text").lower() or "text"
MAMGA_LOG_MAX_BYTES = _env_int("MAMGA_LOG_MAX_BYTES", 5 * 1024 * 1024)
MAMGA_LOG_BACKUP_COUNT = _env_int("MAMGA_LOG_BACKUP_COUNT", 5)
MAMGA_LOG_TO_STDOUT = _env_bool("MAMGA_LOG_TO_STDOUT", True)

# Debug
MAMGA_DEBUG_CANDIDATES = _env_bool("MAMGA_DEBUG_CANDIDATES", False)


PROJECT_ROOT = Path(".")
