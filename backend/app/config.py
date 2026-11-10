"""应用配置。

从 backend/.env 读取（内置极简解析，不依赖 python-dotenv）。
密码等敏感信息只写在 .env，绝不硬编码进代码。

运行环境分两类：
- 阶段 0/1 数据管道：D:\\py\\python.exe（xtquant + pymysql/aiomysql/sqlalchemy/pandas）
- 阶段 2/3 数据层 + agent：tradingagents conda 环境（akshare + pymysql + stockstats
  + langgraph + langchain-openai，见 backend/README.md 环境说明）
"""
from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/


def _load_env() -> None:
    """极简 .env 解析：只补 os.environ 中缺失的键，不覆盖已有环境变量。"""
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env()


class Config:
    # ---- MySQL ----
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")
    SOURCE_DB = os.getenv("SOURCE_DB", "fastapi_db")    # 只读源库，严禁写入
    TARGET_DB = os.getenv("TARGET_DB", "ashare_agent")  # 自建库，唯一写入目标

    # ---- QMT / xtquant ----
    QMT_ADDR = os.getenv("QMT_ADDR", "127.0.0.1")
    QMT_PORT = int(os.getenv("QMT_PORT", "58610"))

    # ---- LLM（DeepSeek 双模型分级）----
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")
    DEEP_THINK_LLM = os.getenv("DEEP_THINK_LLM", "deepseek-v4-pro")
    QUICK_THINK_LLM = os.getenv("QUICK_THINK_LLM", "deepseek-v4-flash")
    BACKEND_URL = os.getenv("BACKEND_URL", "https://api.deepseek.com/v1")
    OUTPUT_LANGUAGE = os.getenv("OUTPUT_LANGUAGE", "Chinese")
    MAX_DEBATE_ROUNDS = int(os.getenv("MAX_DEBATE_ROUNDS", "1"))
    MAX_RISK_DISCUSS_ROUNDS = int(os.getenv("MAX_RISK_DISCUSS_ROUNDS", "1"))
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

    # ---- API（阶段 4 FastAPI + SSE）----
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))

    @classmethod
    def llm_config(cls) -> dict:
        """组装成 TradingAgentsGraph 期望的 config dict（见 app/graph/trading_graph.py）。"""
        return {
            "llm_provider": cls.LLM_PROVIDER,
            "deep_think_llm": cls.DEEP_THINK_LLM,
            "quick_think_llm": cls.QUICK_THINK_LLM,
            "backend_url": cls.BACKEND_URL,
            "output_language": cls.OUTPUT_LANGUAGE,
            "max_debate_rounds": cls.MAX_DEBATE_ROUNDS,
            "max_risk_discuss_rounds": cls.MAX_RISK_DISCUSS_ROUNDS,
        }


def check_credentials() -> None:
    """启动前显式校验，避免误连。"""
    if not Config.DB_PASSWORD:
        raise RuntimeError("DB_PASSWORD 未配置：请在 backend/.env 中填写")
    if not Config.DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置：请在 backend/.env 中填写")
