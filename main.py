"""
=============================================================================
📚 Educational Material Generator (edu-generator)
=============================================================================
Purpose: Generate beginner-friendly programming tutorials from ANY repository.
Architecture: PM (GPT) + Scout (Gemini Flash) + Scribe (Gemini Flash)

Usage:
  1. Add this repo as a submodule to your project
  2. Create a config.yaml in your project root
  3. Run: python edu-generator/main.py --config config.yaml

Safety Features:
- Max iterations per task: 3 (prevents infinite loops)
- Max RPM: 10 (rate limiting)
- Excluded directories: node_modules, .next, dist, coverage, etc.
- Cost estimation before execution

Language Rules:
- Inter-agent communication: English only
- Final output (tutorials): Japanese (です・ます style)

Prompt Management:
- All prompts are stored in prompts/ directory
- Hover over imported constants in VS Code to see Japanese translations
=============================================================================
"""

import argparse
import io
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import yaml
# Pydantic config validation (型安全な設定検証)
from config_models import EduConfig, validate_config, validate_outline
from crewai import LLM, Agent, Crew, Process, Task
from crewai_tools import DirectoryReadTool, FileReadTool
from dotenv import load_dotenv
# New Multi-PM Architecture Agents
# Legacy Commander (kept for backward compatibility)
from prompt.agent import (  # Judgment Layer (GPT-5.2); Worker Layer (Gemini Flash); Router
  BEGINNER_ADVOCATE_BACKSTORY_TEMPLATE, BEGINNER_ADVOCATE_GOAL,
  BEGINNER_ADVOCATE_ROLE, COMMANDER_BACKSTORY_TEMPLATE, COMMANDER_GOAL,
  COMMANDER_ROLE, CONTENT_PM_BACKSTORY_TEMPLATE, CONTENT_PM_GOAL,
  CONTENT_PM_ROLE, PRODUCT_OWNER_BACKSTORY_TEMPLATE, PRODUCT_OWNER_GOAL,
  PRODUCT_OWNER_ROLE, QUALITY_PM_BACKSTORY_TEMPLATE, QUALITY_PM_GOAL,
  QUALITY_PM_ROLE, ROUTER_BACKSTORY_TEMPLATE, ROUTER_GOAL, ROUTER_ROLE,
  SCOUT_BACKSTORY_TEMPLATE, SCOUT_GOAL, SCOUT_ROLE,
  SCRIBE_BACKSTORY_TEMPLATE, SCRIBE_GOAL, SCRIBE_ROLE,
  VALIDATOR_BACKSTORY_TEMPLATE, VALIDATOR_GOAL, VALIDATOR_ROLE)
from prompt.task.beginner_review import (BEGINNER_REVIEW_EXPECTED_OUTPUT,
                                         BEGINNER_REVIEW_TASK_TEMPLATE)
# New Multi-PM Review Tasks
from prompt.task.content_review import (CONTENT_REVIEW_EXPECTED_OUTPUT,
                                        CONTENT_REVIEW_TASK_TEMPLATE)
from prompt.task.outline import OUTLINE_EXPECTED_OUTPUT, OUTLINE_TASK_TEMPLATE
from prompt.task.po_approval import (PO_APPROVAL_EXPECTED_OUTPUT,
                                     PO_APPROVAL_TASK_TEMPLATE)
from prompt.task.quality_review import (QUALITY_REVIEW_EXPECTED_OUTPUT,
                                        QUALITY_REVIEW_TASK_TEMPLATE)
from prompt.task.quality_rules import QUALITY_RULES
from prompt.task.research import (RESEARCH_EXPECTED_OUTPUT,
                                  RESEARCH_TASK_TEMPLATE)
from prompt.task.review import REVIEW_EXPECTED_OUTPUT, REVIEW_TASK_TEMPLATE
from prompt.task.validation import (VALIDATION_EXPECTED_OUTPUT,
                                    VALIDATION_TASK_TEMPLATE)
# 新しい簡潔版プロンプトをインポート
from prompt.task.write_v2 import (get_write_prompt, WRITE_EXPECTED_OUTPUT)
# 旧版も後方互換のため保持
from prompt.task.write import (IMPROVE_MODE_CONTEXT, WRITE_TASK_TEMPLATE)

# PDF Validation imports
from pdf_validator import PDFValidator

# LLM Judge統合
from utils.llm_judge_helper import (
    run_llm_judge_evaluation,
    format_llm_judge_report,
)

# Prompt imports - hover over these in VS Code to see Japanese translations
# プロンプトインポート - VS Codeでホバーすると日本語訳が表示されます
from prompt import TEACHING_METHODOLOGY

load_dotenv()

# =============================================================================
# 🔒 SAFETY CONFIGURATION (Infinite Loop & Cost Prevention)
# =============================================================================

DEFAULT_CONFIG = {
    "log_dir": "logs",  # ログディレクトリ（.gitignoreに追加済）
    "log_level": "INFO",  # ログレベル（DEBUG, INFO, WARNING, ERROR）
    "safety": {
        "max_iterations": 3,
        "max_retries": 3,
        "max_rpm": 10,
        "timeout_seconds": 1800,
        "cost_confirmation_threshold_usd": 1.0,
    },
    "exclusions": {
        "directories": [
            "node_modules", ".next", "dist", "build", "coverage",
            ".git", ".vercel", "playwright-report", "test-results",
            ".idea", "__pycache__", ".pnp", "out", "edu-creator",
        ],
        "patterns": ["*.log", "*.env*", "*.db", "*.db-*", "*.local", "*.pem", "*.py"],
    },
    "llm": {
        # モデルは.envから読み込み、未設定時のデフォルト値
        # WORKER_MODEL_OVERRIDE環境変数で上書き可能 (例: gemini-2.0-flash, claude-code)
        "commander_model": os.getenv("OPENAI_MODEL", "gpt-5.2"),
        "worker_model": os.getenv("WORKER_MODEL_OVERRIDE") or os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"),
        "commander_temperature": 0.2,
        "worker_temperature": 0.4,
    },
}

# =============================================================================
# ⏱️ RATE LIMITING (Gemini Flash Free Tier: 15 RPM)
# =============================================================================
GEMINI_RATE_LIMIT_DELAY = 60  # 60秒待機（15 RPM対応、安全マージン付き）

# =============================================================================
# 📖 TEACHING METHODOLOGY (Imported from prompt/teaching.py)
# =============================================================================
# TEACHING_METHODOLOGY is imported from prompt/teaching.py
# Hover over it to see the Japanese translation
# 教育方針は prompt/teaching.py からインポート
# ホバーすると日本語訳が表示されます


# =============================================================================
# 📦 FILE CACHE (Automatic invalidation on file modification)
# =============================================================================

class FileCache:
    """
    Simple file cache with automatic invalidation based on mtime.
    ファイル更新時刻に基づく自動無効化付きファイルキャッシュ。
    """

    def __init__(self, cache_file: str = ".file_cache.json", enabled: bool = True):
        self.cache_file = Path(cache_file)
        self.enabled = enabled
        self.cache: dict[str, dict[str, Any]] = {}
        self.stats = {"hits": 0, "misses": 0, "invalidations": 0}
        self._load()

    def _load(self) -> None:
        """Load cache from disk if exists."""
        if not self.enabled:
            return

        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception as e:
                print(f"⚠️  Failed to load cache: {e}")
                self.cache = {}

    def _save(self) -> None:
        """Save cache to disk."""
        if not self.enabled:
            return

        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  Failed to save cache: {e}")

    def get(self, file_path: str) -> Optional[str]:
        """
        Get file content from cache if valid.
        ファイルがキャッシュにあり、更新されていなければ内容を返す。
        """
        if not self.enabled:
            return None

        abs_path = str(Path(file_path).resolve())

        # ファイルが存在しない場合はキャッシュも無効
        if not Path(abs_path).exists():
            return None

        # ファイルの最終更新時刻を取得
        try:
            current_mtime = os.path.getmtime(abs_path)
        except OSError:
            return None

        # キャッシュに存在するか確認
        if abs_path in self.cache:
            cached_mtime = self.cache[abs_path].get("mtime")
            if cached_mtime == current_mtime:
                # キャッシュヒット
                self.stats["hits"] += 1
                return self.cache[abs_path]["content"]
            else:
                # ファイルが更新されているので無効化
                self.stats["invalidations"] += 1
                del self.cache[abs_path]

        # キャッシュミス
        self.stats["misses"] += 1
        return None

    def set(self, file_path: str, content: str) -> None:
        """
        Store file content in cache with mtime.
        ファイル内容とmtimeをキャッシュに保存。
        """
        if not self.enabled:
            return

        abs_path = str(Path(file_path).resolve())

        try:
            mtime = os.path.getmtime(abs_path)
            self.cache[abs_path] = {"content": content, "mtime": mtime}
            self._save()
        except OSError as e:
            print(f"⚠️  Failed to cache {file_path}: {e}")

    def clear(self) -> None:
        """Clear all cache."""
        self.cache = {}
        self.stats = {"hits": 0, "misses": 0, "invalidations": 0}
        if self.cache_file.exists():
            self.cache_file.unlink()

    def print_stats(self) -> None:
        """Print cache statistics."""
        if not self.enabled:
            print("📦 Cache: Disabled")
            return

        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0

        print("\n" + "=" * 60)
        print("📦 File Cache Statistics")
        print("=" * 60)
        print(f"   Cache hits: {self.stats['hits']}")
        print(f"   Cache misses: {self.stats['misses']}")
        print(f"   Auto invalidations: {self.stats['invalidations']}")
        print(f"   Hit rate: {hit_rate:.1f}%")
        print(f"   Total cached files: {len(self.cache)}")
        print("=" * 60 + "\n")


# Global cache instance (initialized in main())
# グローバルキャッシュインスタンス（main()で初期化）
_file_cache: Optional[FileCache] = None


FORBIDDEN_REPLACEMENTS = {
    "同じように": "具体的に同じ手順を1つずつ書いてください",
    "残りも": "残りの対象も個別に同じ手順を実行してください",
    "以下略": "省略せずに全ての手順を書いてください",
    "簡単です": "順番に進めれば実行できます",
}


def sanitize_markdown(content: str) -> str:
    """Remove outer code fences, normalize headings, and trim whitespace."""
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()

    # Replace forbidden phrases to satisfy quality rules.
    for bad, replacement in FORBIDDEN_REPLACEMENTS.items():
        stripped = stripped.replace(bad, replacement)

    # Ensure step headings start with "### ステップ" (emoji comes after for regex compatibility).
    fixed_lines: list[str] = []
    step_heading_pattern = re.compile(r"^(###)\s+[^\s]*\s*(ステップ[0-9０-９]+)")
    for line in stripped.splitlines():
        if line.startswith("###") and "ステップ" in line:
            line = step_heading_pattern.sub(r"\1 \2", line)
            if line.startswith("### ステップ") and not re.search(r"[🀀-🿿😀-🙏]", line):
                line = line + " 🧭"
        fixed_lines.append(line)

    return "\n".join(fixed_lines).strip() + "\n"


# Global repository root for path resolution
_repo_root: Path | None = None


class CachedFileReadTool(FileReadTool):
    """
    FileReadTool with automatic caching and repository root awareness.
    自動キャッシュ付きFileReadTool(リポジトリルート自動解決機能付き)。
    
    Note: Caches full file content only (ignores start_line/line_count for caching).
    This avoids cache key complexity while still providing performance benefits.
    """

    def _normalize_args(
        self,
        file_path: Any = None,
        start_line: Any = 1,
        line_count: Any = None,
    ) -> tuple[str | None, int, int | None]:
        if isinstance(file_path, dict):
            args = file_path
            file_path = args.get("file_path") or args.get("path")
            start_line = args.get("start_line", start_line)
            line_count = args.get("line_count", line_count)
        elif isinstance(file_path, (tuple, list)):
            for item in file_path:
                if isinstance(item, dict):
                    return self._normalize_args(item, start_line, line_count)
                if isinstance(item, str):
                    file_path = item
                    break

        if file_path is not None and not isinstance(file_path, str):
            file_path = str(file_path)

        start_line = self._unwrap_scalar(start_line)
        line_count = self._unwrap_scalar(line_count)

        try:
            normalized_start_line = int(start_line or 1)
        except (TypeError, ValueError):
            normalized_start_line = 1

        try:
            normalized_line_count = int(line_count) if line_count is not None else None
        except (TypeError, ValueError):
            normalized_line_count = None

        return file_path, normalized_start_line, normalized_line_count

    @staticmethod
    def _unwrap_scalar(value: Any) -> Any:
        """dict/tuple/listで渡ってきた値から、その中身のスカラー値を取り出す。

        Toolの引数はLLM側の呼び出し形式によりコンテナで包まれて届くことがあり、
        素通しでint()に渡すと変換に失敗して既定値へ黙って落ちてしまう
        （start_lineは1、line_countはNone＝ファイル全体扱いになる）。
        """
        if isinstance(value, dict):
            for key in ("value", "start_line", "line_count"):
                if key in value:
                    return value[key]
            return next(iter(value.values()), None) if value else None
        if isinstance(value, (tuple, list)):
            return value[0] if value else None
        return value

    def _resolve_path(self, file_path: str) -> str:
        """Resolve relative paths against repository root."""
        global _repo_root
        path = Path(file_path)
        if path.is_absolute():
            return str(path)
        if _repo_root:
            return str(_repo_root / file_path)
        return str(Path(file_path).resolve())

    def _run(
        self,
        file_path: Any = None,
        start_line: Any = 1,
        line_count: Any = None,
    ) -> str:
        """Override _run to add caching layer and support partial reads."""
        global _file_cache

        file_path, start_line, line_count = self._normalize_args(
            file_path or self.file_path,
            start_line,
            line_count,
        )

        if not file_path:
            raise ValueError("file_path must be provided")

        # 相対パスを解決
        resolved_path = self._resolve_path(file_path)

        # キャッシュが有効かつ存在する場合
        if _file_cache and _file_cache.enabled:
            cached_content = _file_cache.get(resolved_path)
            if cached_content is not None:
                # キャッシュされた全体から部分を切り出し
                if start_line or line_count:
                    lines = cached_content.splitlines(keepends=True)
                    start_idx = max((start_line - 1) if start_line else 0, 0)
                    end_idx = (start_idx + line_count) if line_count else len(lines)
                    selected_lines = lines[start_idx:end_idx]
                    if not selected_lines and start_idx > 0:
                        return f"Error: Start line {start_line} exceeds the number of lines in the file."
                    return ''.join(selected_lines)
                return cached_content

        # キャッシュミス → 実際にファイルを読む
        content = super()._run(
            file_path=resolved_path,
            start_line=start_line,
            line_count=line_count,
        )

        # ファイル全体をキャッシュに保存(部分読み込みの場合も全体を読み直してキャッシュ)
        if _file_cache and _file_cache.enabled:
            # 部分読み込みの場合は全体を再読み込みしてキャッシュ
            if start_line != 1 or line_count is not None:
                full_content = super()._run(file_path=resolved_path, start_line=1, line_count=None)
                _file_cache.set(resolved_path, full_content)
            else:
                _file_cache.set(resolved_path, content)

        return content


# =============================================================================
# ⚙️ CONFIGURATION LOADER
# =============================================================================

def load_config(config_path: str) -> dict[str, Any]:
    """
    Load and validate config with Pydantic (型安全な設定検証)

    型安全な検証を行う：
    - YAMLパース → Pydantic検証 → 型安全な設定オブジェクト
    - ValidationError発生時はエラーメッセージを表示して終了
    - ZodのsafeParseと同じ概念の「事前検証」

    Args:
        config_path: YAML設定ファイルのパス

    Returns:
        検証済みの設定辞書（Pydantic経由）

    Raises:
        SystemExit: 設定検証失敗時（エラーメッセージ付き）
    """
    # デフォルト設定と結合
    config_dict = DEFAULT_CONFIG.copy()

    if config_path and Path(config_path).exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}

            # Deep merge user config into defaults
            for key, value in user_config.items():
                if isinstance(value, dict) and key in config_dict:
                    config_dict[key].update(value)
                else:
                    config_dict[key] = value

        except yaml.YAMLError as e:
            print(f"❌ YAML parsing error: {e}")
            sys.exit(1)
    else:
        print(f"⚠️  Config file not found: {config_path}")
        print("   Using default configuration.")

    # 環境変数による上書き（最優先）
    if os.getenv("WORKER_MODEL_OVERRIDE"):
        config_dict["llm"]["worker_model"] = os.getenv("WORKER_MODEL_OVERRIDE")
    
    # Pydantic検証（ZodのsafeParser相当）
    success, validated_config, error_msg = validate_config(config_dict)

    if not success:
        print("\n" + "=" * 70)
        print("❌ CONFIG VALIDATION FAILED")
        print("=" * 70)
        print(error_msg)
        print("\nご指摘の点を修正して、再度実行してください。")
        print("=" * 70 + "\n")
        sys.exit(1)

    # Pydantic検証済みのオブジェクトを辞書に変換して返す
    config_dict_validated = validated_config.model_dump()

    print("\n" + "=" * 70)
    print("✅ CONFIG VALIDATION PASSED")
    print("=" * 70)
    print(f"📚 Chapters to generate: {len(config_dict_validated.get('chapters', []))}")
    print(f"🔒 Safety max_iterations: {config_dict_validated['safety']['max_iterations']}")
    print(f"🤖 Commander model: {config_dict_validated['llm']['commander_model']}")
    worker_model = config_dict_validated['llm']['worker_model']
    worker_override = " (WORKER_MODEL_OVERRIDE)" if os.getenv("WORKER_MODEL_OVERRIDE") else ""
    print(f"⚡ Worker model: {worker_model}{worker_override}")
    print("=" * 70 + "\n")

    return config_dict_validated


def get_teaching_method(config: dict[str, Any]) -> str:
    """
    Get teaching method from config or use default from prompts/teaching.py.

    設定ファイルまたはprompts/teaching.pyのデフォルトから教育方針を取得。
    """
    # Use imported TEACHING_METHODOLOGY from prompts/teaching.py
    # prompts/teaching.pyからインポートしたTEACHING_METHODOLOGYを使用
    return TEACHING_METHODOLOGY


# =============================================================================
# 📋 LOGGING SETUP
# =============================================================================

def setup_logging_for_chapter(chapter_log_dir: Path, log_level: str = "INFO") -> tuple[logging.FileHandler, io.StringIO]:
    """
    Setup logging handlers for chapter execution.

    Returns: (file_handler, string_buffer)
    - file_handler: ファイルに出力するハンドラー
    - string_buffer: 画面とファイルの両方に出力するためのバッファー

    Creates:
    - logs/day01/crew_output.log: CrewAI verbose output
    """
    # Create logger for chapter
    chapter_logger = logging.getLogger(f"chapter_{chapter_log_dir.name}")
    chapter_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    chapter_logger.handlers = []

    # File handler for crew_output.log
    log_file = chapter_log_dir / "crew_output.log"
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    chapter_logger.addHandler(file_handler)

    # StringIO buffer for console + file dual output
    string_buffer = io.StringIO()

    return file_handler, string_buffer


# =============================================================================
# 🤖 LLM CONFIGURATION
# =============================================================================

def create_worker_llm(config: dict[str, Any]):
    """
    Create Gemini LLM for Scout and Scribe (FREE tier).

    Uses CrewAI's native LLM class with LiteLLM backend.
    Model format: gemini/gemini-2.0-flash (LiteLLM requires provider prefix)

    Scout/Scribe用のGemini LLMを作成（無料枠）。
    CrewAIネイティブのLLMクラスをLiteLLMバックエンドで使用。
    モデル形式: gemini/gemini-2.0-flash（LiteLLMはプロバイダープレフィックスが必要）
    """
    llm_config = config.get("llm", {})

    # Get model name and ensure it has the gemini/ prefix for LiteLLM
    # モデル名を取得し、LiteLLM用にgemini/プレフィックスを確保
    model_name = llm_config.get("worker_model", os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"))
    if not model_name.startswith("gemini/"):
        model_name = f"gemini/{model_name}"

    return LLM(
        model=model_name,
        temperature=llm_config.get("worker_temperature", 0.4),
        api_key=os.getenv("GOOGLE_API_KEY"),
    )


def create_commander_llm(config: dict[str, Any]):
    """
    Create GPT LLM for Commander (PAID - use sparingly).

    Uses CrewAI's native LLM class with LiteLLM backend.
    Model format: openai/gpt-5.2 (LiteLLM requires provider prefix for some models)

    Commander用のGPT LLMを作成（有料 - 節約して使用）。
    CrewAIネイティブのLLMクラスをLiteLLMバックエンドで使用。
    モデル形式: openai/gpt-5.2（LiteLLMは一部モデルでプロバイダープレフィックスが必要）
    """
    llm_config = config.get("llm", {})

    # Get model name - OpenAI models work with or without prefix
    # モデル名を取得 - OpenAIモデルはプレフィックスあり/なしどちらでも動作
    model_name = llm_config.get("commander_model", os.getenv("OPENAI_MODEL", "gpt-5.2"))

    return LLM(
        model=model_name,
        temperature=llm_config.get("commander_temperature", 0.2),
        api_key=os.getenv("OPENAI_API_KEY"),
    )


def get_agent_llm(config: dict[str, Any], agent_name: str, default_layer: str) -> LLM:
    """
    Get LLM for a specific agent with fallback chain.

    エージェント用LLMを優先順位に従って取得する。

    Priority:
    1. agent_models[agent_name] - Per-agent specific configuration
    2. commander_model/worker_model - Layer default (based on default_layer)

    Args:
        config: Configuration dictionary
        agent_name: Agent name (e.g., "scout", "product_owner")
        default_layer: Default layer ("commander" or "worker")

    Returns:
        LLM instance for the agent
    """
    llm_config = config.get("llm", {})
    agent_models = llm_config.get("agent_models")

    # Priority 1: Per-agent override
    if agent_models and agent_name in agent_models:
        agent_cfg = agent_models[agent_name]
        model_name = agent_cfg.get("model") if isinstance(agent_cfg, dict) else agent_cfg.model
        temperature = agent_cfg.get("temperature", 0.4) if isinstance(agent_cfg, dict) else agent_cfg.temperature

        # Detect provider and add prefix if needed
        if "gemini" in model_name.lower() and not model_name.startswith("gemini/"):
            model_name = f"gemini/{model_name}"
            api_key = os.getenv("GOOGLE_API_KEY")
        elif "claude" in model_name.lower() and not model_name.startswith("anthropic/"):
            model_name = f"anthropic/{model_name}"
            api_key = os.getenv("ANTHROPIC_API_KEY")
        else:
            api_key = os.getenv("OPENAI_API_KEY")

        print(f"  📌 {agent_name}: Using custom LLM → {model_name} (temp={temperature})")
        return LLM(model=model_name, temperature=temperature, api_key=api_key)

    # Priority 2: Layer default
    if default_layer == "commander":
        return create_commander_llm(config)
    return create_worker_llm(config)


def create_router_llm(config: dict[str, Any]) -> LLM | None:
    """
    Create LLM for Router agent (optional).

    Routerエージェント用のLLMを作成する（オプション）。
    router_modelが設定されている場合のみ有効。

    Returns:
        LLM instance or None if router_model is not configured
    """
    llm_config = config.get("llm", {})
    router_model = llm_config.get("router_model")

    if not router_model:
        return None

    router_temp = llm_config.get("router_temperature", 0.1)

    # Detect provider and add prefix if needed
    if "gemini" in router_model.lower() and not router_model.startswith("gemini/"):
        router_model = f"gemini/{router_model}"
        api_key = os.getenv("GOOGLE_API_KEY")
    elif "claude" in router_model.lower() and not router_model.startswith("anthropic/"):
        router_model = f"anthropic/{router_model}"
        api_key = os.getenv("ANTHROPIC_API_KEY")
    else:
        api_key = os.getenv("OPENAI_API_KEY")

    print(f"  🔀 Router: Using LLM → {router_model} (temp={router_temp})")
    return LLM(model=router_model, temperature=router_temp, api_key=api_key)


# =============================================================================
# 👤 AGENT FACTORY
# =============================================================================

def create_agents(config: dict[str, Any], repo_root: Path):
    """
    Create all agents with configuration.

    Architecture:
    - Judgment Layer (GPT-5.2): PO, ContentPM, QualityPM, BeginnerAdvocate
    - Worker Layer (Gemini Flash): Scout, Scribe, Validator

    All agent prompts are imported from prompt/agent/ directory.
    Hover over the imported constants to see Japanese translations.

    アーキテクチャ:
    - 判断層（GPT-5.2）: PO, ContentPM, QualityPM, BeginnerAdvocate
    - 作業層（Gemini Flash）: Scout, Scribe, Validator

    全エージェントを設定付きで作成。
    エージェントプロンプトは prompt/agent/ からインポート。
    インポートした定数にホバーすると日本語訳が表示されます。
    """
    safety = config.get("safety", {})
    exclusions = config.get("exclusions", {})
    teaching_method = get_teaching_method(config)

    max_iterations = safety.get("max_iterations", 3)
    excluded_dirs = exclusions.get("directories", [])
    excluded_patterns = exclusions.get("patterns", [])

    # Initialize LLMs with per-agent configuration support
    # LLMを初期化（エージェント個別設定をサポート）
    #
    # Priority: agent_models[agent_name] > commander_model/worker_model
    # 優先順位: agent_models[agent_name] > commander_model/worker_model
    print("\n🤖 Initializing Agent LLMs...")

    # Check if custom agent_models are configured
    llm_config = config.get("llm", {})
    if llm_config.get("agent_models"):
        print("   📌 Custom agent_models detected - using per-agent configuration")
    else:
        print("   📦 Using default 2-layer architecture (commander/worker)")

    # Define source directory (AI will auto-detect if not specified)
    src_dir = repo_root / config.get("paths", {}).get("src_dir", "src")

    # Ensure screenshots directory exists
    screenshots_dir = repo_root / "material" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # Set global repository root for path resolution
    global _repo_root
    _repo_root = repo_root

    # Tools (use cached version for file reading with repo root awareness)
    scout_tools = [
        DirectoryReadTool(directory=str(src_dir)),
        CachedFileReadTool(),
    ]
    scribe_tools = [CachedFileReadTool()]
    review_tools = [CachedFileReadTool()]

    # ==========================================================================
    # 🎯 JUDGMENT LAYER (GPT-5.2) - 判断層
    # ==========================================================================

    # --- Product Owner (PO) ---
    # 最終承認権限を持つプロダクトオーナー
    # Prompt imported from prompt/agent/product_owner.py
    product_owner_backstory = PRODUCT_OWNER_BACKSTORY_TEMPLATE.format(
        max_iterations=max_iterations,
        teaching_method=teaching_method,
    )
    product_owner = Agent(
        role=PRODUCT_OWNER_ROLE,
        goal=PRODUCT_OWNER_GOAL,
        backstory=product_owner_backstory,
        tools=review_tools,
        llm=get_agent_llm(config, "product_owner", "commander"),
        verbose=True,
        allow_delegation=True,
        max_iter=max_iterations,
    )

    # --- Content PM ---
    # 構成・フロー・ストーリーテリング担当PM
    # Prompt imported from prompt/agent/content_pm.py
    content_pm_backstory = CONTENT_PM_BACKSTORY_TEMPLATE.format(
        max_iterations=max_iterations,
        teaching_method=teaching_method,
    )
    content_pm = Agent(
        role=CONTENT_PM_ROLE,
        goal=CONTENT_PM_GOAL,
        backstory=content_pm_backstory,
        tools=review_tools,
        llm=get_agent_llm(config, "content_pm", "commander"),
        verbose=True,
        max_iter=max_iterations,
    )

    # --- Quality PM ---
    # 技術的正確性・コード検証担当PM
    # Prompt imported from prompt/agent/quality_pm.py
    quality_pm_backstory = QUALITY_PM_BACKSTORY_TEMPLATE.format(
        max_iterations=max_iterations,
    )
    quality_pm = Agent(
        role=QUALITY_PM_ROLE,
        goal=QUALITY_PM_GOAL,
        backstory=quality_pm_backstory,
        tools=review_tools,
        llm=get_agent_llm(config, "quality_pm", "commander"),
        verbose=True,
        max_iter=max_iterations,
    )

    # --- Beginner Advocate ---
    # 初心者視点代弁者
    # Prompt imported from prompt/agent/beginner_advocate.py
    beginner_advocate_backstory = BEGINNER_ADVOCATE_BACKSTORY_TEMPLATE.format(
        max_iterations=max_iterations,
    )
    beginner_advocate = Agent(
        role=BEGINNER_ADVOCATE_ROLE,
        goal=BEGINNER_ADVOCATE_GOAL,
        backstory=beginner_advocate_backstory,
        tools=review_tools,
        llm=get_agent_llm(config, "beginner_advocate", "commander"),
        verbose=True,
        max_iter=max_iterations,
    )

    # ==========================================================================
    # ⚡ WORKER LAYER (Gemini Flash) - 作業層
    # ==========================================================================

    # --- Scout ---
    # リポジトリ調査担当
    # Prompt imported from prompt/agent/scout.py
    scout_backstory = SCOUT_BACKSTORY_TEMPLATE.format(
        excluded_dirs=", ".join(excluded_dirs),
        excluded_patterns=", ".join(excluded_patterns),
    )
    scout = Agent(
        role=SCOUT_ROLE,
        goal=SCOUT_GOAL,
        backstory=scout_backstory,
        tools=scout_tools,
        llm=get_agent_llm(config, "scout", "worker"),
        verbose=True,
        max_iter=max_iterations,
    )

    # --- Scribe ---
    # チュートリアル執筆担当
    # Prompt imported from prompt/agent/scribe.py
    scribe_backstory = SCRIBE_BACKSTORY_TEMPLATE.format(
        teaching_method=teaching_method,
    )
    scribe = Agent(
        role=SCRIBE_ROLE,
        goal=SCRIBE_GOAL,
        backstory=scribe_backstory,
        tools=scribe_tools,
        llm=get_agent_llm(config, "scribe", "worker"),
        verbose=True,
        max_iter=max_iterations,
    )

    # --- Validator ---
    # コマンド・コード検証担当 + 自動品質チェックツール統合
    # Prompt imported from prompt/agent/validator.py
    validator_backstory = VALIDATOR_BACKSTORY_TEMPLATE.format(
        max_iterations=max_iterations,
    )
    
    # Import Validator tools (automatic quality checking)
    try:
        from prompt.agent.validator import validate_markdown_structure
        validator_tools = scribe_tools + [validate_markdown_structure]
    except ImportError:
        print("⚠️  validate_markdown_structure tool not available, using file tools only")
        validator_tools = scribe_tools
    
    validator = Agent(
        role=VALIDATOR_ROLE,
        goal=VALIDATOR_GOAL,
        backstory=validator_backstory,
        tools=validator_tools,  # ファイル読み込み + 自動品質チェック
        llm=get_agent_llm(config, "validator", "worker"),
        verbose=True,
        max_iter=max_iterations,
    )

    # Return all agents as a named tuple for clarity
    # 明確さのために全エージェントを辞書で返す
    return {
        # Judgment Layer (GPT-5.2)
        "product_owner": product_owner,
        "content_pm": content_pm,
        "quality_pm": quality_pm,
        "beginner_advocate": beginner_advocate,
        # Worker Layer (Gemini Flash)
        "scout": scout,
        "scribe": scribe,
        "validator": validator,
    }


def create_router_agent(config: dict[str, Any], max_iterations: int = 3) -> Agent | None:
    """
    Create Router agent for task distribution (optional).

    Routerエージェントを作成する（オプション）。
    router_modelが設定されている場合のみ有効。

    The Router agent acts as a manager in hierarchical process mode,
    analyzing tasks and delegating them to the most suitable agent.

    Args:
        config: Configuration dictionary
        max_iterations: Maximum delegation iterations

    Returns:
        Router Agent or None if router_model is not configured
    """
    router_llm = create_router_llm(config)
    if router_llm is None:
        return None

    router_backstory = ROUTER_BACKSTORY_TEMPLATE.format(
        max_iterations=max_iterations,
    )

    return Agent(
        role=ROUTER_ROLE,
        goal=ROUTER_GOAL,
        backstory=router_backstory,
        llm=router_llm,
        verbose=True,
        allow_delegation=True,
        max_iter=max_iterations,
    )


# =============================================================================
# 📝 TASK DEFINITIONS
# =============================================================================

def create_tasks_for_chapter(
    chapter: dict[str, Any],
    agents: dict[str, Agent],
    config: dict[str, Any],
    output_dir: Path,
    examples_context: str = "",
    existing_content: str | None = None,
    generation_mode: str = "create",
) -> list[Task]:
    """
    Create the Multi-PM task pipeline for a single chapter.

    Pipeline:
    1. Scout: Research repository
    2. ContentPM: Create outline (structure/flow focus)
    3. Scribe: Write tutorial
    4. Validator: Verify commands/code (parallel with PM reviews)
    5. ContentPM: Review structure/flow
    6. QualityPM: Review technical accuracy
    7. BeginnerAdvocate: Review from beginner perspective
    8. ProductOwner: Final approval based on all reviews

    マルチPMタスクパイプラインを単一チャプター用に作成。
    """
    # Extract agents from dictionary
    product_owner = agents["product_owner"]
    content_pm = agents["content_pm"]
    quality_pm = agents["quality_pm"]
    beginner_advocate = agents["beginner_advocate"]
    scout = agents["scout"]
    scribe = agents["scribe"]
    validator = agents["validator"]

    safety = config.get("safety", {})
    max_iterations = safety.get("max_iterations", 3)

    chapter_id = chapter["id"]
    chapter_title = chapter["title"]
    chapter_subtitle = chapter.get("subtitle", "")
    topics = ", ".join(chapter.get("topics", []))
    target_dirs = ", ".join(chapter.get("target_dirs", ["src/"]))

    output_file = str(output_dir / f"{chapter_id}_{chapter_title.replace(' ', '_')}.md")

    # ==========================================================================
    # PHASE 1: RESEARCH & PLANNING
    # ==========================================================================

    # Task 1: Research (Scout - Gemini Flash)
    research_description = RESEARCH_TASK_TEMPLATE.format(
        chapter_title=chapter_title,
        chapter_subtitle=chapter_subtitle,
        topics=topics,
        target_dirs=target_dirs,
    ) + (f"\n\n---\n{examples_context}" if examples_context else "")
    task_research = Task(
        description=research_description,
        expected_output=RESEARCH_EXPECTED_OUTPUT,
        agent=scout,
    )

    # Task 2: Outline (ContentPM - GPT-5.2)
    # ContentPMが構成・フロー重視でアウトライン作成
    outline_description = OUTLINE_TASK_TEMPLATE.format(
        chapter_title=chapter_title,
        chapter_subtitle=chapter_subtitle,
        max_iterations=max_iterations,
    ) + (f"\n\n---\n{examples_context}" if examples_context else "")
    task_outline = Task(
        description=outline_description,
        expected_output=OUTLINE_EXPECTED_OUTPUT,
        agent=content_pm,
        context=[task_research],
    )

    # ==========================================================================
    # PHASE 2: WRITING
    # ==========================================================================

    # Task 3: Writing (Scribe - Gemini Flash)
    # 新しい簡潔版プロンプトを使用
    write_description = get_write_prompt(
        chapter_title=chapter_title,
        chapter_subtitle=chapter_subtitle,
        day_number=int(chapter_id.replace("day", "")),
        outline="{previous_task_output}",  # Crewが自動で前タスクの出力を埋める
        research_results="{previous_task_output}",
        existing_content=existing_content if generation_mode == "improve" else "",
    )

    task_write = Task(
        description=write_description,
        expected_output=WRITE_EXPECTED_OUTPUT,
        agent=scribe,
        context=[task_outline, task_research],
    )

    # ==========================================================================
    # PHASE 3: MULTI-PM REVIEW (Parallel where possible)
    # ==========================================================================

    # Task 4: Validation (Validator - Gemini Flash)
    # コマンド・コードの検証
    validation_description = VALIDATION_TASK_TEMPLATE.format(
        chapter_title=chapter_title,
    )
    task_validation = Task(
        description=validation_description,
        expected_output=VALIDATION_EXPECTED_OUTPUT,
        agent=validator,
        context=[task_write, task_research],
    )

    # Task 5: Content Review (ContentPM - GPT-5.2)
    # 構成・フロー・ストーリーテリングのレビュー
    content_review_description = CONTENT_REVIEW_TASK_TEMPLATE.format(
        chapter_title=chapter_title,
    )
    task_content_review = Task(
        description=content_review_description,
        expected_output=CONTENT_REVIEW_EXPECTED_OUTPUT,
        agent=content_pm,
        context=[task_write],
    )

    # Task 6: Quality Review (QualityPM - GPT-5.2)
    # 技術的正確性のレビュー
    quality_review_description = QUALITY_REVIEW_TASK_TEMPLATE.format(
        chapter_title=chapter_title,
    )
    task_quality_review = Task(
        description=quality_review_description,
        expected_output=QUALITY_REVIEW_EXPECTED_OUTPUT,
        agent=quality_pm,
        context=[task_write, task_research],
    )

    # Task 7: Beginner Review (BeginnerAdvocate - GPT-5.2)
    # 初心者視点のレビュー
    beginner_review_description = BEGINNER_REVIEW_TASK_TEMPLATE.format(
        chapter_title=chapter_title,
    )
    task_beginner_review = Task(
        description=beginner_review_description,
        expected_output=BEGINNER_REVIEW_EXPECTED_OUTPUT,
        agent=beginner_advocate,
        context=[task_write],
    )

    # ==========================================================================
    # PHASE 4: FINAL APPROVAL
    # ==========================================================================

    # Task 8: Product Owner Approval (PO - GPT-5.2)
    # 全レビューを統合して最終承認
    po_approval_description = PO_APPROVAL_TASK_TEMPLATE.format(
        chapter_title=chapter_title,
    )
    task_po_approval = Task(
        description=po_approval_description,
        expected_output=PO_APPROVAL_EXPECTED_OUTPUT,
        agent=product_owner,
        context=[
            task_write,
            task_validation,
            task_content_review,
            task_quality_review,
            task_beginner_review,
        ],
        output_file=output_file,
    )

    return [
        task_research,
        task_outline,
        task_write,
        task_validation,
        task_content_review,
        task_quality_review,
        task_beginner_review,
        task_po_approval,
    ]


# =============================================================================
# 🚀 EXECUTION
# =============================================================================

def estimate_cost(num_chapters: int, config: dict[str, Any]) -> dict[str, Any]:
    """
    Estimate API costs before execution.

    Multi-PM Architecture:
    - GPT-5.2 (Judgment Layer): PO, ContentPM, QualityPM, BeginnerAdvocate
      - 4 agents × ~2000 tokens each = ~8000 tokens/chapter
    - Gemini Flash (Worker Layer): Scout, Scribe, Validator
      - 3 agents × ~20000 tokens each = ~60000 tokens/chapter (FREE tier)
    """
    # GPT-5.2: 4 judgment agents with ~2000 tokens each
    gpt_tokens_per_chapter = 8000
    # Gemini Flash: 3 worker agents (FREE tier)
    gemini_tokens_per_chapter = 60000
    # GPT-5.2 pricing (approximate)
    gpt_cost_per_1k = 0.03

    total_gpt_tokens = gpt_tokens_per_chapter * num_chapters
    total_gemini_tokens = gemini_tokens_per_chapter * num_chapters
    estimated_cost = (total_gpt_tokens / 1000) * gpt_cost_per_1k

    return {
        "num_chapters": num_chapters,
        "gpt_tokens": total_gpt_tokens,
        "gemini_tokens": total_gemini_tokens,
        "estimated_cost_usd": round(estimated_cost, 2),
        "gemini_within_free_tier": total_gemini_tokens < 1_000_000,
        # Multi-PM architecture info
        "architecture": {
            "judgment_layer": ["ProductOwner", "ContentPM", "QualityPM", "BeginnerAdvocate"],
            "worker_layer": ["Scout", "Scribe", "Validator"],
        },
    }


# =============================================================================
# ⏱️ PROGRESS TRACKER
# =============================================================================

class ProgressTracker:
    """
    Track progress and estimate remaining time for chapter generation.

    チャプター生成の進捗を追跡し、残り時間を推定する。
    """

    def __init__(self, total_chapters: int, tasks_per_chapter: int = 8):
        """
        Initialize progress tracker.

        Args:
            total_chapters: Total number of chapters to generate
            tasks_per_chapter: Number of tasks per chapter (default: 8 - Multi-PM pipeline)
                              Research, Outline, Write, Validation,
                              Content Review, Quality Review, Beginner Review, PO Approval
        """
        self.total_chapters = total_chapters
        self.tasks_per_chapter = tasks_per_chapter
        self.total_tasks = total_chapters * tasks_per_chapter

        self.start_time: float | None = None
        self.chapter_times: list[float] = []
        self.current_chapter = 0
        self.current_task = 0

        # 最初のチャプターの推定時間（秒）- 実測後に更新
        # Estimated time for first chapter (seconds) - updated after measurement
        self.estimated_chapter_time = 300  # 5分をデフォルト推定

    def start(self) -> None:
        """Start the progress tracker."""
        self.start_time = time.time()
        self._print_header()

    def _print_header(self) -> None:
        """Print initial progress header."""
        print("\n" + "=" * 70)
        print("⏱️  PROGRESS TRACKER")
        print("=" * 70)
        print(f"📚 Total chapters: {self.total_chapters}")
        print(f"📝 Tasks per chapter: {self.tasks_per_chapter}")
        print(f"🕐 Started at: {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 70 + "\n")

    def start_chapter(self, chapter_num: int, chapter_title: str) -> float:
        """
        Mark the start of a chapter and return start time.

        チャプターの開始をマークし、開始時刻を返す。
        """
        self.current_chapter = chapter_num
        chapter_start = time.time()

        # 推定残り時間を計算
        remaining_chapters = self.total_chapters - chapter_num + 1
        if self.chapter_times:
            avg_time = sum(self.chapter_times) / len(self.chapter_times)
            estimated_remaining = avg_time * remaining_chapters
        else:
            estimated_remaining = self.estimated_chapter_time * remaining_chapters

        eta = datetime.now() + timedelta(seconds=estimated_remaining)

        print("\n" + "╔" + "═" * 68 + "╗")
        print(f"║ 📚 Chapter {chapter_num}/{self.total_chapters}: {chapter_title[:50]:<50} ║")
        print("╠" + "═" * 68 + "╣")
        print(f"║ ⏱️  Estimated remaining: {self._format_duration(estimated_remaining):<43} ║")
        print(f"║ 🏁 ETA: {eta.strftime('%H:%M:%S'):<55} ║")
        print("╚" + "═" * 68 + "╝\n")

        return chapter_start

    def end_chapter(self, chapter_start: float) -> None:
        """
        Mark the end of a chapter and update statistics.

        チャプターの終了をマークし、統計を更新する。
        """
        chapter_duration = time.time() - chapter_start
        self.chapter_times.append(chapter_duration)

        # 次回の推定時間を更新
        self.estimated_chapter_time = sum(self.chapter_times) / len(self.chapter_times)

        print(f"\n✅ Chapter completed in {self._format_duration(chapter_duration)}")

    def print_task_progress(self, task_name: str, task_num: int) -> None:
        """
        Print progress for current task.

        現在のタスクの進捗を表示する。
        """
        total_tasks_done = (self.current_chapter - 1) * self.tasks_per_chapter + task_num
        overall_progress = (total_tasks_done / self.total_tasks) * 100

        elapsed = time.time() - (self.start_time or time.time())
        if total_tasks_done > 0:
            estimated_total = elapsed / total_tasks_done * self.total_tasks
            remaining = estimated_total - elapsed
        else:
            remaining = self.estimated_chapter_time * self.total_chapters

        progress_bar = self._create_progress_bar(overall_progress)

        print(f"├── 📋 Task {task_num}/{self.tasks_per_chapter}: {task_name}")
        print(f"│   {progress_bar} {overall_progress:.1f}%")
        print(f"│   ⏱️  Remaining: ~{self._format_duration(remaining)}")

    def print_final_summary(self) -> None:
        """Print final summary after all chapters are complete."""
        if not self.start_time:
            return

        total_duration = time.time() - self.start_time
        avg_chapter_time = sum(self.chapter_times) / len(self.chapter_times) if self.chapter_times else 0

        print("\n" + "═" * 70)
        print("🎉 GENERATION COMPLETE!")
        print("═" * 70)
        print(f"📚 Chapters generated: {len(self.chapter_times)}/{self.total_chapters}")
        print(f"⏱️  Total time: {self._format_duration(total_duration)}")
        print(f"📊 Average per chapter: {self._format_duration(avg_chapter_time)}")
        print(f"🏁 Finished at: {datetime.now().strftime('%H:%M:%S')}")
        print("═" * 70 + "\n")

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}分{secs}秒"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}時間{minutes}分"

    def _create_progress_bar(self, percentage: float, width: int = 30) -> str:
        """Create a visual progress bar."""
        filled = int(width * percentage / 100)
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}]"


# =============================================================================
# 📄 PDF GENERATION & VALIDATION
# =============================================================================

def generate_and_validate_pdf(
    markdown_file: Path,
    repo_root: Path,
    max_attempts: int = 3,
) -> tuple[bool, str, list[dict[str, Any]]]:
    """
    Generate PDF from Markdown and validate it for visual/structural issues.

    Args:
        markdown_file: Path to the markdown file
        repo_root: Repository root directory (for finding CSS/output paths)
        max_attempts: Maximum validation attempts (not used for auto-fix yet)

    Returns:
        Tuple of (passed: bool, pdf_path: str, issues: list)
    """
    import subprocess

    # Convert to absolute paths to avoid working directory issues
    markdown_file = Path(markdown_file).resolve()
    repo_root = Path(repo_root).resolve()

    # Determine paths
    pdf_dir = repo_root / "material" / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    pdf_filename = markdown_file.stem + ".pdf"
    pdf_path = pdf_dir / pdf_filename
    css_path = repo_root / "material" / "style" / "tutorial.css"

    log_messages = []
    log_messages.append(f"\n{'='*60}")
    log_messages.append("📄 PDF GENERATION & VALIDATION")
    log_messages.append(f"{'='*60}")
    log_messages.append(f"  Source: {markdown_file.name}")
    log_messages.append(f"  Output: {pdf_path}")

    # Check if CSS exists
    if not css_path.exists():
        log_messages.append(f"  ⚠️  CSS not found: {css_path}")
        css_arg = []
    else:
        css_arg = ["--stylesheet", str(css_path)]

    # Generate PDF using md-mermaid-to-pdf
    try:
        cmd = ["npx", "md-mermaid-to-pdf", str(markdown_file), str(pdf_path)] + css_arg
        log_messages.append(f"  Command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(repo_root),
        )

        if result.returncode != 0:
            log_messages.append(f"  ❌ PDF generation failed!")
            log_messages.append(f"  stderr: {result.stderr[:500]}")
            print("\n".join(log_messages))
            return False, "", [{"type": "error", "message": "PDF generation failed", "severity": "high"}]

        log_messages.append(f"  ✅ PDF generated successfully")

    except subprocess.TimeoutExpired:
        log_messages.append(f"  ❌ PDF generation timed out (120s)")
        print("\n".join(log_messages))
        return False, "", [{"type": "error", "message": "PDF generation timeout", "severity": "high"}]
    except FileNotFoundError:
        log_messages.append(f"  ❌ npx/md-mermaid-to-pdf not found")
        log_messages.append(f"     Install with: npm install -g md-mermaid-to-pdf")
        print("\n".join(log_messages))
        return False, "", [{"type": "error", "message": "md-mermaid-to-pdf not installed", "severity": "high"}]

    # Validate the generated PDF
    log_messages.append(f"\n  🔍 Validating PDF...")

    try:
        validator = PDFValidator(str(pdf_path))
        validation_result = validator.validate()

        issues = validation_result.get("issues", [])
        passed = validation_result.get("passed", False)
        page_count = validation_result.get("page_count", 0)

        log_messages.append(f"  Pages: {page_count}")
        log_messages.append(f"  Issues found: {len(issues)}")

        if passed:
            log_messages.append(f"  ✅ PDF validation PASSED")
        else:
            log_messages.append(f"  ⚠️  PDF validation found issues:")
            # Group issues by severity
            high = [i for i in issues if i.get("severity") == "high"]
            medium = [i for i in issues if i.get("severity") == "medium"]

            if high:
                log_messages.append(f"    HIGH SEVERITY ({len(high)}):")
                for issue in high[:3]:  # Show first 3
                    page_info = f" (p.{issue['page']})" if "page" in issue else ""
                    log_messages.append(f"      - {issue['message']}{page_info}")

            if medium:
                log_messages.append(f"    MEDIUM SEVERITY ({len(medium)}):")
                for issue in medium[:2]:  # Show first 2
                    page_info = f" (p.{issue['page']})" if "page" in issue else ""
                    log_messages.append(f"      - {issue['message']}{page_info}")

        print("\n".join(log_messages))
        return passed, str(pdf_path), issues

    except FileNotFoundError:
        log_messages.append(f"  ❌ Generated PDF not found: {pdf_path}")
        print("\n".join(log_messages))
        return False, "", [{"type": "error", "message": "PDF file not found after generation", "severity": "high"}]
    except Exception as e:
        log_messages.append(f"  ❌ PDF validation error: {e}")
        print("\n".join(log_messages))
        return False, str(pdf_path), [{"type": "error", "message": f"Validation error: {e}", "severity": "high"}]


# =============================================================================
# 🔄 PDF GENERATION WITH AUTO-FIX LOOP
# =============================================================================

def generate_and_validate_pdf_with_fix(
    markdown_file: Path,
    repo_root: Path,
    scribe_agent: Agent,
    context_tasks: list[Task],
    max_attempts: int = 3,
) -> tuple[bool, str, list[dict[str, Any]]]:
    """
    Generate PDF, validate, and auto-fix issues in a loop.

    Flow:
    1. Generate PDF
    2. Validate PDF
    3. If issues found:
       3.1 Apply automatic fixes (code-based)
       3.2 Generate LLM fix instructions for Scribe agent
       3.3 Regenerate PDF
    4. Repeat until max_attempts or passed

    Args:
        markdown_file: Path to the markdown file
        repo_root: Repository root directory
        scribe_agent: Scribe agent for LLM-based fixes
        context_tasks: Context tasks for Scribe agent
        max_attempts: Maximum number of fix attempts

    Returns:
        Tuple of (passed: bool, pdf_path: str, issues: list)
    """
    from pdf_fixer import PDFFixer, create_pdf_fix_prompt

    markdown_file = Path(markdown_file).resolve()

    for attempt in range(1, max_attempts + 1):
        print(f"\n{'='*60}")
        print(f"📄 PDF Generation Attempt {attempt}/{max_attempts}")
        print(f"{'='*60}")

        # Step 1: Generate and validate PDF
        passed, pdf_path, issues = generate_and_validate_pdf(
            markdown_file, repo_root, max_attempts=1
        )

        if passed:
            print(f"✅ PDF validation PASSED on attempt {attempt}")
            return True, pdf_path, issues

        if attempt == max_attempts:
            print(f"\n⚠️  PDF validation still failing after {max_attempts} attempts")
            print("   Please review the PDF manually for remaining issues")
            return False, pdf_path, issues

        # Step 2: Filter issues that need fixing
        fixable_issues = [
            i for i in issues
            if i.get("severity") in ("high", "medium")
            and i.get("type") not in ("error",)  # Skip fatal errors
        ]

        if not fixable_issues:
            print("   No fixable issues detected, but validation failed")
            return False, pdf_path, issues

        print(f"\n🔧 Attempting to fix {len(fixable_issues)} issue(s)...")

        # Step 3: Apply automatic fixes
        fixer = PDFFixer(markdown_file, fixable_issues)
        fixed_content = fixer.auto_fix_content()

        if fixer.applied_fixes:
            print(f"   Auto-fix: {fixer.get_fix_summary()}")
            markdown_file.write_text(fixed_content, encoding="utf-8")

        # Step 4: Generate LLM fix instructions
        llm_instructions = fixer.generate_fix_instructions()

        if llm_instructions and scribe_agent:
            print(f"   LLM fix: {len(llm_instructions)} instruction(s) for Scribe agent")

            fix_prompt = create_pdf_fix_prompt(llm_instructions)

            # Create a fix task for Scribe
            current_content = markdown_file.read_text(encoding="utf-8")

            fix_task = Task(
                description=f"""
現在のMarkdownファイルを以下の指示に従って修正してください。

{fix_prompt}

【現在のファイル内容】
```markdown
{current_content[:10000]}...
```

修正後のMarkdownファイル全体を出力してください。
""",
                expected_output="修正されたMarkdownチュートリアル（ファイル全体）",
                agent=scribe_agent,
                context=context_tasks,
            )

            try:
                # Execute fix with Scribe agent
                crew = Crew(
                    agents=[scribe_agent],
                    tasks=[fix_task],
                    process=Process.sequential,
                    verbose=False,
                )
                result = crew.kickoff()

                # Extract and save fixed content
                fixed_markdown = str(result.raw) if hasattr(result, "raw") else str(result)

                # Clean up markdown fences if present
                if fixed_markdown.startswith("```markdown"):
                    fixed_markdown = fixed_markdown[len("```markdown"):].strip()
                if fixed_markdown.endswith("```"):
                    fixed_markdown = fixed_markdown[:-3].strip()

                # Validate the fixed content has reasonable length
                if len(fixed_markdown) > len(current_content) * 0.5:
                    markdown_file.write_text(fixed_markdown, encoding="utf-8")
                    print(f"   ✅ Scribe agent applied fixes ({len(fixed_markdown)} chars)")
                else:
                    print(f"   ⚠️  Scribe agent output too short, keeping original")

            except Exception as e:
                print(f"   ⚠️  Scribe agent fix failed: {e}")
                # Continue with next attempt anyway

    return False, pdf_path, issues


# =============================================================================
# 🔍 QUALITY VALIDATION & AUTO-FIX LOOP
# =============================================================================

def validate_and_fix_quality(
    output_file: Path,
    scribe_agent: Agent,
    task_outline: Task,
    task_research: Task,
    chapter: dict[str, Any],
    repo_root: Path,
    max_attempts: int = 5,
) -> tuple[bool, int, str]:
    """
    Validate generated tutorial against quality rules and auto-fix if needed.

    Returns:
        tuple: (passed: bool, attempts: int, validation_log: str)
    """
    import subprocess

    log_messages = []

    for attempt in range(1, max_attempts + 1):
        log_msg = f"\n🔍 Quality Check (Attempt {attempt}/{max_attempts})..."
        print(log_msg)
        log_messages.append(log_msg)

        # Run quality check script
        # スクリプトは repo_root/script/ にある（edu-creator内ではない）
        check_script = repo_root / "script" / "check_quality.sh"
        if not check_script.exists():
            log_msg = f"⚠️  Quality check script not found: {check_script}"
            print(log_msg)
            log_messages.append(log_msg)
            return True, attempt, "\n".join(log_messages)  # Skip if script doesn't exist

        try:
            result = subprocess.run(
                ["bash", str(check_script), str(output_file)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=repo_root,
            )

            check_output = result.stdout + result.stderr
            log_messages.append(check_output)

            # Check if all tests passed
            if result.returncode == 0 and "PASS" in check_output and "FAIL" not in check_output:
                log_msg = f"✅ Quality check PASSED on attempt {attempt}!"
                print(log_msg)
                log_messages.append(log_msg)
                return True, attempt, "\n".join(log_messages)

            # If last attempt, return without fixing
            if attempt == max_attempts:
                log_msg = f"\n⚠️  Quality check still failing after {max_attempts} attempts."
                log_msg += f"\nPlease review manually:\n{check_output[:500]}"
                print(log_msg)
                log_messages.append(log_msg)
                return False, attempt, "\n".join(log_messages)

            # Parse failures and create fix prompt
            log_msg = f"\n🔧 Attempting to fix quality issues (attempt {attempt}/{max_attempts})..."
            print(log_msg)
            log_messages.append(log_msg)

            # Parse specific failures from check output
            fix_instructions = []

            # Step 1: Forbidden words
            if "Step 1" in check_output and ("❌" in check_output or "禁止ワード" in check_output):
                forbidden_matches = re.findall(r"❌.*?(同じように|残りも|以下略|簡単です|同様に)", check_output)
                if forbidden_matches:
                    fix_instructions.append(f"❌ 禁止ワードを削除してください: {', '.join(set(forbidden_matches))}")

            # Step 2: Code/paragraph length
            if "Step 2" in check_output:
                # Check for code block length violations
                code_matches = re.findall(r"コードブロック.*?([0-9]+)行.*?L([0-9]+)", check_output)
                if code_matches:
                    for lines, line_num in code_matches:
                        fix_instructions.append(f"⚠️ L{line_num}のコードブロック（{lines}行）を25行以下に短縮してください")

                # Check for paragraph length violations
                para_matches = re.findall(r"段落.*?L([0-9]+).*?([0-9]+)文", check_output)
                if para_matches:
                    for line_num, sentences in para_matches:
                        sentences_int = int(sentences)
                        fix_instructions.append(f"⚠️ L{line_num}の段落（{sentences}文）を3文以下に分割してください")
                        # Add specific guidance on how to split
                        if sentences_int == 4:
                            fix_instructions.append("   → 1文目+2文目 を1段落に、3文目+4文目 を別段落に分割")
                        elif sentences_int >= 5:
                            split_count = (sentences_int + 2) // 3
                            fix_instructions.append(f"   → 約{split_count}つの段落に分割（各3文程度）")
                            fix_instructions.append("   → 文と文の間に空行を入れて、複数段落に分割してください")

            # Step 3: Visualization elements
            if "Step 3" in check_output:
                # Check table count
                table_matches = re.findall(r"表.*?([0-9]+)個", check_output)
                if table_matches:
                    current_tables = int(table_matches[0])
                    if current_tables < 4:
                        needed = 4 - current_tables
                        fix_instructions.append(f"📊 表を{needed}個追加してください（現在{current_tables}個、目標4個以上）")
                        fix_instructions.append("   推奨：コマンド比較表、環境変数一覧表、トラブルシューティング表、ツール比較表など")

                # Check Mermaid diagrams
                mermaid_matches = re.findall(r"Mermaid.*?([0-9]+)個", check_output)
                if mermaid_matches:
                    current_mermaid = int(mermaid_matches[0])
                    if current_mermaid < 1:
                        fix_instructions.append("📈 Mermaid図を1個以上追加してください")
                        fix_instructions.append("   推奨：アーキテクチャ図、フロー図、依存関係図など")

            # Create detailed fix prompt for Scribe
            if not fix_instructions:
                fix_instructions.append("チェック結果を確認し、品質ルールを全て満たすように修正してください")

            fix_prompt = f"""
【品質チェック結果の修正指示】

以下の問題を修正してください：

{chr(10).join(f"{i+1}. {instr}" for i, instr in enumerate(fix_instructions))}

修正手順：
1. 現在のMarkdownファイルを読み込む
2. 上記の各問題を順番に修正する
3. 修正後、Markdownファイル全体を出力する

【重要な注意事項】
- 既存の内容を削除せず、必要な修正のみを行う
- 日本語です・ます調を維持
- 技術的な正確性を失わない
- コードブロックの前後に必ず説明を入れる
- 表は | で正しくフォーマットする
- Mermaid図は ```mermaid で開始し ``` で終了する

修正後のMarkdownファイル全体を出力してください。
"""

            # Get current content
            current_content = output_file.read_text(encoding="utf-8")

            # Create a task to fix the issues
            fix_task = Task(
                description=fix_prompt,
                expected_output="修正されたMarkdownチュートリアル",
                agent=scribe_agent,
                context=[task_outline, task_research],
            )

            # Execute fix task
            crew = Crew(
                agents=[scribe_agent],
                tasks=[fix_task],
                process=Process.sequential,
                verbose=False,
            )

            fix_result = crew.kickoff()

            # Save fixed content
            fixed_content = sanitize_markdown(str(fix_result))
            if fixed_content and len(fixed_content) > 100:
                output_file.write_text(fixed_content, encoding="utf-8")
                log_msg = f"✏️  Content updated. Re-checking quality..."
                print(log_msg)
                log_messages.append(log_msg)
            else:
                log_msg = f"⚠️  Fix attempt {attempt} produced invalid output"
                print(log_msg)
                log_messages.append(log_msg)

        except subprocess.TimeoutExpired:
            log_msg = "⚠️  Quality check timed out"
            print(log_msg)
            log_messages.append(log_msg)
            return False, attempt, "\n".join(log_messages)
        except Exception as e:
            log_msg = f"⚠️  Error during quality check: {e}"
            print(log_msg)
            log_messages.append(log_msg)
            return False, attempt, "\n".join(log_messages)

    return False, max_attempts, "\n".join(log_messages)


def find_existing_chapter_file(chapter: dict[str, Any], output_dir: Path) -> Path | None:
    """
    Find existing chapter file if it exists.

    既存のチャプターファイルを探す。
    ファイル名パターン: {chapter_id}_{title}.md または {chapter_id}_*.md
    """
    chapter_id = chapter["id"]
    chapter_title_clean = chapter["title"].replace(" ", "_")

    # Exact match first
    exact_file = output_dir / f"{chapter_id}_{chapter_title_clean}.md"
    if exact_file.exists():
        return exact_file

    # Pattern match (in case title changed)
    for file in output_dir.glob(f"{chapter_id}_*.md"):
        return file

    return None


def find_all_existing_files(output_dir: Path) -> list[Path]:
    """
    Find all existing day*.md files in output directory.

    output_dir内の既存の day*.md ファイルをすべて検出する。
    quality_report や _new などの派生ファイルは除外。
    """
    files = []
    for file in sorted(output_dir.glob("day[0-3][0-9]_*.md")):
        # Skip quality reports and backup files
        if "_quality_report" in file.name or "_new" in file.name:
            continue
        files.append(file)
    return files


def find_files_in_range(output_dir: Path, start_day: int, end_day: int) -> list[Path]:
    """
    Find existing day*.md files within a specific range.

    指定範囲内の day*.md ファイルを検出する。
    例: start_day=1, end_day=10 → day01〜day10
    """
    files = []
    for day_num in range(start_day, end_day + 1):
        day_id = f"day{day_num:02d}"
        for file in output_dir.glob(f"{day_id}_*.md"):
            # Skip quality reports and backup files
            if "_quality_report" in file.name or "_new" in file.name:
                continue
            files.append(file)
    return sorted(files)


def parse_range(range_str: str) -> tuple[int, int] | None:
    """
    Parse range string like '1-10' or '5-15'.

    '1-10' や '5-15' のような範囲文字列をパースする。
    """
    try:
        parts = range_str.split("-")
        if len(parts) == 2:
            start = int(parts[0])
            end = int(parts[1])
            if 1 <= start <= end <= 30:
                return (start, end)
    except ValueError:
        pass
    return None


def run_chapter(
    chapter: dict[str, Any],
    agents: dict[str, Agent],
    config: dict[str, Any],
    output_dir: Path,
    progress: ProgressTracker | None = None,
    chapter_num: int = 1,
    log_dir: Path | None = None,
    update_file: Path | None = None,
) -> str:
    """Generate tutorial for a single chapter with comprehensive logging support."""
    safety = config.get("safety", {})
    log_level = config.get("log_level", "INFO")
    chapter_title = f"{chapter['title']} {chapter.get('subtitle', '')}"
    chapter_id = chapter["id"]

    # Setup logging for this chapter
    file_handler = None
    chapter_log_dir = None
    metadata = {
        "chapter_id": chapter_id,
        "chapter_title": chapter_title,
        "chapter_num": chapter_num,
        "start_time": datetime.now().isoformat(),
        "log_level": log_level,
    }

    if log_dir:
        chapter_log_dir = Path(log_dir) / chapter_id
        chapter_log_dir.mkdir(parents=True, exist_ok=True)
        file_handler, _ = setup_logging_for_chapter(chapter_log_dir, log_level)
        metadata["log_dir"] = str(chapter_log_dir)

    # Add examples context if available
    examples_context = ""
    examples_list = []
    if "examples" in config and config["examples"]:
        examples_context = "\n\n📚 REFERENCE EXAMPLES:\n"
        for ex_path in config["examples"]:
            if Path(ex_path).exists():
                examples_context += f"- {Path(ex_path).name}\n"
                examples_list.append(Path(ex_path).name)
            else:
                examples_context += f"- {ex_path} (not found)\n"
        metadata["examples"] = examples_list

    # ========================================================================
    # 🔄 MODE DETECTION (Update vs Create)
    # ========================================================================
    existing_content: str | None = None
    existing_file: Path | None = None

    if update_file:
        # --update mode: use specified file
        existing_file = update_file
        existing_content = existing_file.read_text(encoding="utf-8")
        mode = "update"
        print(f"\n📄 Update target: {existing_file.name}")
        print(f"   Mode: UPDATE (improving existing content)")
        print(f"   Size: {len(existing_content)} characters")
    else:
        # No --update: create new file
        mode = "create"
        print(f"\n📄 Mode: CREATE (generating new file)")

    metadata["generation_mode"] = mode
    if existing_file:
        metadata["existing_file"] = str(existing_file)

    # 進捗トラッカーで開始時刻を記録
    chapter_start = None
    if progress:
        chapter_start = progress.start_chapter(chapter_num, chapter_title)
    else:
        print(f"\n{'='*60}")
        print(f"📚 Generating: {chapter_title}")
        print(f"{'='*60}\n")

    tasks = create_tasks_for_chapter(
        chapter, agents, config, output_dir, examples_context,
        existing_content=existing_content,
        generation_mode=mode,
    )

    # タスク名のリスト（進捗表示用）- 新しいマルチPMパイプライン
    task_names = [
        "Research (Scout)",
        "Outline (ContentPM)",
        "Write (Scribe)",
        "Validation (Validator)",
        "Content Review (ContentPM)",
        "Quality Review (QualityPM)",
        "Beginner Review (BeginnerAdvocate)",
        "Final Approval (ProductOwner)",
    ]

    # タスクごとの進捗コールバックを設定
    if progress:
        for i, (task, name) in enumerate(zip(tasks, task_names), 1):
            progress.print_task_progress(name, i)

    # Setup stdout capture for verbose logging
    old_stdout = None
    log_file_handle = None
    try:
        if chapter_log_dir:
            old_stdout = sys.stdout
            log_file_path = chapter_log_dir / "crew_output.log"
            log_file_handle = open(log_file_path, "w", encoding="utf-8")

            # Tee stdout to both console and file
            class TeeOutput:
                def __init__(self, console, log_file):
                    self.console = console
                    self.log_file = log_file

                def write(self, text):
                    self.console.write(text)
                    self.console.flush()
                    if self.log_file:
                        self.log_file.write(text)
                        self.log_file.flush()

                def flush(self):
                    self.console.flush()
                    if self.log_file:
                        self.log_file.flush()

                def isatty(self):
                    return self.console.isatty()

            sys.stdout = TeeOutput(old_stdout, log_file_handle)

        # Check if Router agent is configured
        # Routerエージェントが設定されているか確認
        router_agent = create_router_agent(config, max_iterations=safety.get("max_iterations", 3))

        if router_agent:
            # Hierarchical mode with Router as manager
            # Routerをマネージャーとしたhierarchicalモード
            print("\n🔀 Router agent enabled - using hierarchical process")
            crew = Crew(
                agents=list(agents.values()),  # dict -> list of Agent objects
                tasks=tasks,
                process=Process.hierarchical,
                manager_agent=router_agent,
                max_rpm=safety.get("max_rpm", 10),
                verbose=True,
            )
        else:
            # Sequential mode (default, backward compatible)
            # sequentialモード（デフォルト、後方互換）
            crew = Crew(
                agents=list(agents.values()),  # dict -> list of Agent objects
                tasks=tasks,
                process=Process.sequential,
                max_rpm=safety.get("max_rpm", 10),
                verbose=True,
            )

        result = crew.kickoff()

    finally:
        # Restore stdout
        if old_stdout:
            sys.stdout = old_stdout
        if log_file_handle:
            log_file_handle.close()
        if file_handler:
            file_handler.close()

    # ========================================================================
    # Save task outputs to individual markdown files
    # ========================================================================
    if chapter_log_dir:
        task_outputs = {}
        if hasattr(result, 'tasks_output') and result.tasks_output:
            for i, task_output in enumerate(result.tasks_output):
                if i < len(task_names):
                    task_key = task_names[i].split(" (")[0].lower().replace(" ", "_")
                    task_file = chapter_log_dir / f"task_{task_key}.md"
                    task_outputs[task_key] = str(task_output)
                    task_file.write_text(str(task_output), encoding="utf-8")
                    print(f"📝 Task output saved: {task_file.name}")
        metadata["task_outputs_saved"] = list(task_outputs.keys())

    # Log thinking/reasoning if available
    if chapter_log_dir and hasattr(result, "thinking"):
        thinking_log = chapter_log_dir / "thinking.md"
        thinking_log.write_text(result.thinking, encoding="utf-8")
        print(f"\n🧠 Thinking process saved: {thinking_log}")
        print("\n--- THINKING SUMMARY ---")
        # 思考プロセスの最初の500文字を表示
        preview = result.thinking[:500]
        print(preview + ("..." if len(result.thinking) > 500 else ""))
        print("-" * 50)

    # Save metadata
    if chapter_log_dir:
        metadata["end_time"] = datetime.now().isoformat()
        metadata_file = chapter_log_dir / "metadata.json"
        metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n📊 Metadata saved: {metadata_file.name}")

    # チャプター完了を記録
    if progress and chapter_start:
        progress.end_chapter(chapter_start)

    # ファイルに出力（task_write の結果を保存）
    # Save the generated tutorial to file
    chapter_title_clean = chapter["title"].replace(" ", "_")
    output_file = output_dir / f"{chapter_id}_{chapter_title_clean}.md"

    try:
        # task_write（3番目のタスク）の出力を取得
        # Get the output from task_write (3rd task in the list)
        task_write_output = None

        if hasattr(result, 'tasks_output') and len(result.tasks_output) >= 3:
            # CrewAI v0.28+ では task_output から取得
            task_write_output = result.tasks_output[2]
        elif isinstance(result, str):
            # 文字列の場合はそのまま使用
            task_write_output = result

        if not task_write_output:
            # fallback: result を直接使用
            task_write_output = str(result) if result else "エラー: コンテンツが生成されませんでした"

        # ファイルに書き込み
        content = str(task_write_output)
        content = sanitize_markdown(content)
        output_file.write_text(content, encoding="utf-8")
        print(f"\n✅ Tutorial saved: {output_file}")
        print(f"   Size: {len(content)} characters")

        # ========================================================================
        # 🔍 AUTO-QUALITY VALIDATION & FIX LOOP
        # ========================================================================
        print("\n" + "="*60)
        print("🔍 Starting automatic quality validation...")
        print("="*60)

        # Get repo root from output_dir
        repo_root = output_dir.parent if output_dir.parent.name != "material" else output_dir.parent.parent

        # ========================================================================
        # LLM-as-Judge評価（GPT-4o）
        # ========================================================================
        print("\n📊 LLM-as-Judge Evaluation (GPT-4o)...")
        llm_passed, llm_result, llm_message = run_llm_judge_evaluation(
            markdown_file=output_file,
            model="gpt-4o",
            min_passing_score=4.0,
        )
        print(llm_message)

        # LLM Judge結果をログに保存
        if chapter_log_dir and llm_result:
            llm_report = format_llm_judge_report(llm_result)
            llm_log_file = chapter_log_dir / "llm_judge_evaluation.txt"
            llm_log_file.write_text(llm_report, encoding="utf-8")
            print(f"📋 LLM Judge report saved: {llm_log_file.name}")

        # ========================================================================
        # 機械的品質チェック + 自動修正ループ
        # ========================================================================
        print("\n🔧 Mechanical Quality Check + Auto-Fix Loop...")

        # Validate and auto-fix
        passed, attempts, validation_log = validate_and_fix_quality(
            output_file=output_file,
            scribe_agent=agents[2],  # Scribe is the 3rd agent
            task_outline=tasks[1],   # Outline task
            task_research=tasks[0],  # Research task
            chapter=chapter,
            repo_root=repo_root,
            max_attempts=5,
        )

        # Record validation results in metadata
        metadata["quality_validation"] = {
            "mechanical_check_passed": passed,
            "attempts": attempts,
            "max_attempts": 3,
            "llm_judge_passed": llm_passed,
            "llm_judge_score": llm_result.overall_score if llm_result else None,
            "timestamp": datetime.now().isoformat(),
        }

        # Save validation log
        if chapter_log_dir:
            validation_log_file = chapter_log_dir / "quality_validation.log"
            validation_log_file.write_text(validation_log, encoding="utf-8")
            print(f"\n📋 Validation log saved: {validation_log_file.name}")

        # Summary
        print("\n" + "="*60)
        print("📊 Quality Validation Summary:")
        print("="*60)
        print(f"  LLM Judge (GPT-4o): {'✅ PASS' if llm_passed else '❌ FAIL'}")
        if llm_result:
            print(f"    Score: {llm_result.overall_score:.1f}/5.0")
        print(f"  Mechanical Check: {'✅ PASS' if passed else '❌ FAIL'}")
        print(f"    Attempts: {attempts}")
        overall_passed = llm_passed and passed
        print(f"  Overall: {'✅ PASS' if overall_passed else '⚠️ NEEDS REVIEW'}")
        print("="*60)

        # ========================================================================
        # 📄 PDF GENERATION & VISUAL VALIDATION (with auto-fix)
        # ========================================================================
        pdf_passed, pdf_path, pdf_issues = generate_and_validate_pdf_with_fix(
            markdown_file=output_file,
            repo_root=repo_root,
            scribe_agent=agents["scribe"],  # Scribe agent for LLM-based fixes
            context_tasks=[tasks[0], tasks[1]],  # Research and Outline tasks
            max_attempts=3,
        )

        # Record PDF validation results in metadata
        metadata["pdf_validation"] = {
            "passed": pdf_passed,
            "pdf_path": pdf_path,
            "issues_count": len(pdf_issues),
            "high_severity_count": len([i for i in pdf_issues if i.get("severity") == "high"]),
            "timestamp": datetime.now().isoformat(),
        }

        # Save PDF validation report if there are issues
        if chapter_log_dir and pdf_issues:
            pdf_report_file = chapter_log_dir / "pdf_validation.log"
            pdf_report_lines = [
                "PDF Validation Report",
                "=" * 40,
                f"PDF: {pdf_path}",
                f"Passed: {pdf_passed}",
                f"Issues: {len(pdf_issues)}",
                "",
            ]
            for issue in pdf_issues:
                page_info = f" (p.{issue['page']})" if "page" in issue else ""
                pdf_report_lines.append(f"[{issue.get('severity', 'unknown').upper()}] {issue['message']}{page_info}")
                if "context" in issue:
                    pdf_report_lines.append(f"  Context: {issue['context'][:100]}")
            pdf_report_file.write_text("\n".join(pdf_report_lines), encoding="utf-8")
            print(f"\n📋 PDF validation log saved: {pdf_report_file.name}")

        # PDF Summary
        print("\n" + "="*60)
        if pdf_passed:
            print(f"✅ PDF validation PASSED!")
            print(f"   PDF: {pdf_path}")
        else:
            print(f"⚠️  PDF validation found issues.")
            print(f"   PDF: {pdf_path}")
            print("   Review the PDF manually or check the validation log.")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Failed to save file: {output_file}")
        print(f"   Error: {e}")
        # デバッグ情報
        print(f"   Result type: {type(result)}")
        print(f"   Result: {str(result)[:200]}...")

    return result


def main():
    """Main entry point with safety checks."""
    parser = argparse.ArgumentParser(
        description="Generate educational materials from a repository"
    )
    parser.add_argument(
        "--config", "-c",
        default="edu-config.yaml",
        help="Path to config file (default: edu-config.yaml)"
    )
    parser.add_argument(
        "--chapters", "-n",
        type=int,
        default=1,
        help="Number of chapters to generate (default: 1)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show cost estimate without executing"
    )
    parser.add_argument(
        "--examples",
        nargs="+",
        help="Example files to reference (e.g., material/sample/example1.pdf material/sample/example2.pdf)"
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory to save thinking/reasoning logs (default: logs)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level for detailed output (default: INFO)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable file caching (useful when source files are modified)"
    )
    parser.add_argument(
        "--update",
        type=str,
        metavar="FILE",
        default=None,
        help="Update existing file instead of creating new (specify existing .md file path)"
    )
    parser.add_argument(
        "--update-all",
        action="store_true",
        help="Update all existing .md files in output directory"
    )
    parser.add_argument(
        "--update-range",
        type=str,
        metavar="RANGE",
        default=None,
        help="Update a range of days (e.g., '1-10' for day01 to day10, '5-15' for day05 to day15)"
    )
    parser.add_argument(
        "--create-new",
        action="store_true",
        help="Force create new files even if existing files exist (default: update existing files)"
    )
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Set log level from command line argument
    config["log_level"] = args.log_level

    # Initialize global file cache
    # グローバルファイルキャッシュを初期化
    global _file_cache
    cache_enabled = not args.no_cache
    _file_cache = FileCache(cache_file=".file_cache.json", enabled=cache_enabled)
    if cache_enabled:
        print("📦 File cache: Enabled")
    else:
        print("📦 File cache: Disabled (--no-cache)")

    # Determine paths (AI will auto-detect if not in config)
    config_path = Path(args.config).resolve()
    repo_root = config_path.parent
    output_dir = repo_root / config.get("paths", {}).get("output_dir", "material/30days-curriculum")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create screenshots directory
    screenshots_dir = repo_root / "material" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # Setup logging
    log_dir = repo_root / args.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    config["log_dir"] = str(log_dir)

    # Add examples to config if provided
    if args.examples:
        resolved_examples = [str(repo_root / ex) for ex in args.examples]
        config["examples"] = resolved_examples
        print(f"📚 Using examples: {', '.join(resolved_examples)}")

    print("\n" + "="*60)
    print("📚 Educational Material Generator")
    print("="*60)
    print(f"📁 Repository: {repo_root}")
    print(f"📄 Config: {args.config}")
    print(f"📤 Output: {output_dir}")

    # Get chapters
    chapters = config.get("chapters", [])
    if not chapters:
        print("\n❌ No chapters defined in config!")
        sys.exit(1)

    # ========================================================================
    # 🔄 MODE DETECTION: --update-all, --update-range, --update, or CREATE
    # ========================================================================
    update_files_map: dict[str, Path] = {}  # chapter_id -> file_path
    generation_mode = "create"

    if args.update_all:
        # --update-all: Find all existing files
        existing_files = find_all_existing_files(output_dir)
        if not existing_files:
            print(f"\n❌ Error: No existing .md files found in {output_dir}")
            sys.exit(1)

        generation_mode = "update-all"
        print(f"\n🔄 Generation Mode: UPDATE-ALL ({len(existing_files)} files)")
        for f in existing_files:
            day_id = f.name.split("_")[0]
            update_files_map[day_id] = f
            print(f"   - {f.name}")

        chapters_to_generate = [ch for ch in chapters if ch["id"] in update_files_map]
        if not chapters_to_generate:
            print(f"\n❌ Error: No matching chapters found in config for existing files")
            sys.exit(1)

    elif args.update_range:
        # --update-range: Parse range and find files
        range_result = parse_range(args.update_range)
        if not range_result:
            print(f"\n❌ Error: Invalid range format '{args.update_range}'")
            print("   Expected format: '1-10' or '5-15' (day numbers 1-30)")
            sys.exit(1)

        start_day, end_day = range_result
        existing_files = find_files_in_range(output_dir, start_day, end_day)

        if not existing_files:
            print(f"\n❌ Error: No existing files found for day{start_day:02d} to day{end_day:02d}")
            sys.exit(1)

        generation_mode = "update-range"
        print(f"\n🔄 Generation Mode: UPDATE-RANGE (day{start_day:02d} to day{end_day:02d}, {len(existing_files)} files)")
        for f in existing_files:
            day_id = f.name.split("_")[0]
            update_files_map[day_id] = f
            print(f"   - {f.name}")

        chapters_to_generate = [ch for ch in chapters if ch["id"] in update_files_map]
        if not chapters_to_generate:
            print(f"\n❌ Error: No matching chapters found in config for existing files")
            sys.exit(1)

    elif args.update:
        # --update: Single file update
        update_file_path = Path(args.update)
        if not update_file_path.exists():
            print(f"\n❌ Error: Update file not found: {update_file_path}")
            sys.exit(1)

        day_id = update_file_path.name.split("_")[0]
        update_files_map[day_id] = update_file_path
        generation_mode = "update"
        print(f"\n🔄 Generation Mode: UPDATE (improving existing file: {update_file_path.name})")

        chapters_to_generate = [ch for ch in chapters if ch["id"] == day_id]
        if not chapters_to_generate:
            print(f"\n❌ Error: No matching chapter found in config for {day_id}")
            sys.exit(1)

    elif args.create_new:
        # --create-new: Force create new files
        chapters_to_generate = chapters[:args.chapters]
        print(f"\n🔄 Generation Mode: CREATE (generating {len(chapters_to_generate)} new files)")

    else:
        # DEFAULT: Auto-detect existing files and update them
        # デフォルト: 既存ファイルがあれば更新、なければ新規作成
        chapters_to_generate = chapters[:args.chapters]

        # Check for existing files for these chapters
        for ch in chapters_to_generate:
            existing_file = find_existing_chapter_file(ch, output_dir)
            if existing_file:
                update_files_map[ch["id"]] = existing_file

        if update_files_map:
            # Existing files found - UPDATE mode
            generation_mode = "auto-update"
            print(f"\n🔄 Generation Mode: AUTO-UPDATE (updating {len(update_files_map)} existing files)")
            for day_id, f in update_files_map.items():
                print(f"   - {f.name}")

            # Also list chapters that will be created new
            new_chapters = [ch for ch in chapters_to_generate if ch["id"] not in update_files_map]
            if new_chapters:
                print(f"\n📝 New files to create: {len(new_chapters)}")
                for ch in new_chapters:
                    print(f"   - {ch['id']}_{ch['title']}.md")
        else:
            # No existing files - CREATE mode
            print(f"\n🔄 Generation Mode: CREATE (generating {len(chapters_to_generate)} new files)")

    # Cost estimation
    cost_estimate = estimate_cost(len(chapters_to_generate), config)
    print(f"\n💰 Cost Estimate:")
    print(f"   Chapters: {cost_estimate['num_chapters']}")
    print(f"   GPT Tokens: ~{cost_estimate['gpt_tokens']:,}")
    print(f"   Gemini Tokens: ~{cost_estimate['gemini_tokens']:,}")
    print(f"   Estimated Cost: ${cost_estimate['estimated_cost_usd']}")
    print(f"   Gemini Free Tier: {'✅ Yes' if cost_estimate['gemini_within_free_tier'] else '❌ No'}")

    if args.dry_run:
        print("\n🔍 Dry run complete. No generation performed.")
        sys.exit(0)

    # Safety confirmation
    threshold = config.get("safety", {}).get("cost_confirmation_threshold_usd", 1.0)
    if cost_estimate['estimated_cost_usd'] > threshold:
        confirm = input(f"\n⚠️  Estimated cost > ${threshold}. Continue? (yes/no): ")
        if confirm.lower() != "yes":
            print("Aborted by user.")
            sys.exit(0)

    # Create agents
    agents = create_agents(config, repo_root)

    # 進捗トラッカーを初期化
    progress = ProgressTracker(total_chapters=len(chapters_to_generate))
    progress.start()

    # Generate each chapter
    import glob

    from quality_checker import TutorialQualityChecker

    for i, chapter in enumerate(chapters_to_generate, 1):
        # Get update_file for this chapter if in update mode
        update_file = update_files_map.get(chapter["id"])

        try:
            result = run_chapter(chapter, agents, config, output_dir, progress, i, log_dir, update_file=update_file)
            print(f"\n✅ Completed: {chapter['title']}")

            # Gemini API rate limiting（最後のチャプター以外）
            if i < len(chapters_to_generate):
                worker_model = config['llm']['worker_model']
                if 'gemini' in worker_model.lower():
                    print(f"\n⏳ Gemini rate limiting: Waiting {GEMINI_RATE_LIMIT_DELAY}s to avoid API limits...")
                    time.sleep(GEMINI_RATE_LIMIT_DELAY)

            # 自動品質検証を実行
            chapter_files = glob.glob(str(output_dir / f"{chapter['id']}_*.md"))
            if chapter_files:
                output_file = chapter_files[0]
                print(f"\n🔍 Running automated quality check...\n")

                with open(output_file, "r", encoding="utf-8") as f:
                    content = f.read()

                checker = TutorialQualityChecker(content)
                report = checker.generate_report()
                print(report)

                # レポートをログに保存
                report_file = output_file.replace(".md", "_quality_report.txt")
                with open(report_file, "w", encoding="utf-8") as f:
                    f.write(report)

                # 不合格なら警告を表示
                if not checker.check_all()["is_passed"]:
                    print(f"\n⚠️  Quality check FAILED. Review the report and regenerate if needed.")
                    print(f"📋 Report saved: {report_file}")

            print(f"   Output: {output_dir / chapter['id']}*.md")
        except Exception as e:
            print(f"\n❌ Failed: {chapter['title']}")
            print(f"   Error: {e}")
            continue

    # 最終サマリーを表示
    progress.print_final_summary()

    # キャッシュ統計を表示
    if _file_cache:
        _file_cache.print_stats()

    print(f"📁 Output directory: {output_dir}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
