import os
from pathlib import Path
from typing import Any

from crewai import LLM, Agent
from crewai_tools import DirectoryReadTool, FileReadTool
from prompt.agent import (BEGINNER_ADVOCATE_BACKSTORY_TEMPLATE,
                          BEGINNER_ADVOCATE_GOAL, BEGINNER_ADVOCATE_ROLE,
                          COMMANDER_BACKSTORY_TEMPLATE, COMMANDER_GOAL,
                          COMMANDER_ROLE, CONTENT_PM_BACKSTORY_TEMPLATE,
                          CONTENT_PM_GOAL, CONTENT_PM_ROLE,
                          PRODUCT_OWNER_BACKSTORY_TEMPLATE, PRODUCT_OWNER_GOAL,
                          PRODUCT_OWNER_ROLE,
                          QUALITY_VALIDATOR_BACKSTORY_TEMPLATE,
                          QUALITY_VALIDATOR_GOAL, QUALITY_VALIDATOR_ROLE,
                          SCOUT_BACKSTORY_TEMPLATE, SCOUT_GOAL, SCOUT_ROLE,
                          SCRIBE_BACKSTORY_TEMPLATE, SCRIBE_GOAL, SCRIBE_ROLE)
from utils.cache import CachedFileReadTool

from prompt import TEACHING_METHODOLOGY


def get_teaching_method(config: dict[str, Any]) -> str:
    """
    Get teaching method from config or use default from prompts/teaching.py.

    設定ファイルまたはprompts/teaching.pyのデフォルトから教育方針を取得。
    """
    # Use imported TEACHING_METHODOLOGY from prompts/teaching.py
    # prompts/teaching.pyからインポートしたTEACHING_METHODOLOGYを使用
    return TEACHING_METHODOLOGY


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


def create_reviewer_llm(config: dict[str, Any]):
    """
    Create Gemini 3 Pro LLM for PDF Reviewer (PAID).

    Uses CrewAI's native LLM class with LiteLLM backend.
    """
    llm_config = config.get("llm", {})
    model_name = llm_config.get("reviewer_model", os.getenv("GOOGLE_REVIEWER_MODEL", "gemini-3-pro-preview"))
    if not model_name.startswith("gemini/"):
        model_name = f"gemini/{model_name}"

    # Use separate API key for Gemini Pro (GOOGLE_REVIEWER_API_KEY) if available
    api_key = os.getenv("GOOGLE_REVIEWER_API_KEY") or os.getenv("GOOGLE_API_KEY")

    return LLM(
        model=model_name,
        temperature=llm_config.get("reviewer_temperature", 0.3),
        api_key=api_key,
    )


def create_agents(config: dict[str, Any], repo_root: Path):
    """
    Create all agents with configuration.

    All agent prompts are imported from prompt/agent/ directory.
    Hover over the imported constants to see Japanese translations.

    全エージェントを設定付きで作成。
    エージェントプロンプトは prompt/agent/ からインポート。
    インポートした定数にホバーすると日本語訳が表示されます。
    """

    # --- Helper: Force Language Protocol ---
    def enforce_language_protocol(backstory: str) -> str:
        protocol = """

[SYSTEM ENFORCED COMMUNICATION PROTOCOL]
1. THINKING PROCESS: ENGLISH ONLY. You must think, analyze, and plan in English to maximize intelligence.
2. FINAL OUTPUT: JAPANESE (unless explicitly told otherwise). The user interface is in Japanese.
3. NO HYBRID: Do not mix English thinking in the final Japanese output.
"""
        return backstory + protocol

    safety = config.get("safety", {})
    exclusions = config.get("exclusions", {})
    teaching_method = get_teaching_method(config)

    max_iterations = safety.get("max_iterations", 3)
    excluded_dirs = exclusions.get("directories", [])
    excluded_patterns = exclusions.get("patterns", [])

    # Initialize LLMs
    llm_worker = create_worker_llm(config)
    llm_commander = create_commander_llm(config)
    llm_reviewer = create_reviewer_llm(config)

    # Define source directory
    src_dir = repo_root / config.get("paths", {}).get("src_dir", "src")

    # Tools (use cached version for file reading)
    # ツール（ファイル読み込みはキャッシュ版を使用）
    scout_tools = [
        DirectoryReadTool(directory=str(src_dir)),
        CachedFileReadTool(),
    ]
    scribe_tools = [CachedFileReadTool()]
    commander_tools = [CachedFileReadTool()]

    # --- Agent 1: Commander ---
    # Prompt imported from prompt/agent/commander.py
    # プロンプトは prompts/agents/commander.py からインポート
    commander_backstory = enforce_language_protocol(COMMANDER_BACKSTORY_TEMPLATE.format(
        max_iterations=max_iterations,
        teaching_method=teaching_method,
    ))
    commander = Agent(
        role=COMMANDER_ROLE,
        goal=COMMANDER_GOAL,
        backstory=commander_backstory,
        tools=commander_tools,
        llm=llm_commander,
        verbose=True,
        allow_delegation=True,
        max_iter=max_iterations,
    )

    # --- Agent 2: Scout ---
    # Prompt imported from prompt/agent/scout.py
    # プロンプトは prompts/agents/scout.py からインポート
    scout_backstory = enforce_language_protocol(SCOUT_BACKSTORY_TEMPLATE.format(
        excluded_dirs=", ".join(excluded_dirs),
        excluded_patterns=", ".join(excluded_patterns),
    ))
    scout = Agent(
        role=SCOUT_ROLE,
        goal=SCOUT_GOAL,
        backstory=scout_backstory,
        tools=scout_tools,
        llm=llm_worker,
        verbose=True,
        max_iter=max_iterations,
    )

    # --- Agent 3: Scribe ---
    # Prompt imported from prompt/agent/scribe.py
    # プロンプトは prompts/agents/scribe.py からインポート
    scribe_backstory = enforce_language_protocol(SCRIBE_BACKSTORY_TEMPLATE.format(
        teaching_method=teaching_method,
    ))
    scribe = Agent(
        role=SCRIBE_ROLE,
        goal=SCRIBE_GOAL,
        backstory=scribe_backstory,
        tools=scribe_tools,
        llm=llm_worker,
        verbose=True,
        max_iter=max_iterations,
    )

    # --- Agent 4: Quality Validator ---
    quality_validator = Agent(
        role=QUALITY_VALIDATOR_ROLE,
        goal=QUALITY_VALIDATOR_GOAL,
        backstory=enforce_language_protocol(QUALITY_VALIDATOR_BACKSTORY_TEMPLATE),
        tools=commander_tools,
        llm=llm_worker,
        verbose=True,
        max_iter=max_iterations,
    )

    # --- Agent 5: Product Owner ---
    product_owner = Agent(
        role=PRODUCT_OWNER_ROLE,
        goal=PRODUCT_OWNER_GOAL,
        backstory=enforce_language_protocol(PRODUCT_OWNER_BACKSTORY_TEMPLATE),
        tools=commander_tools,
        llm=llm_commander,
        verbose=True,
        max_iter=max_iterations,
    )

    # --- Agent 6: Content PM ---
    content_pm = Agent(
        role=CONTENT_PM_ROLE,
        goal=CONTENT_PM_GOAL,
        backstory=enforce_language_protocol(CONTENT_PM_BACKSTORY_TEMPLATE),
        tools=commander_tools,
        llm=llm_commander,
        verbose=True,
        max_iter=max_iterations,
    )

    # --- Agent 7: Beginner Advocate ---
    beginner_advocate = Agent(
        role=BEGINNER_ADVOCATE_ROLE,
        goal=BEGINNER_ADVOCATE_GOAL,
        backstory=enforce_language_protocol(BEGINNER_ADVOCATE_BACKSTORY_TEMPLATE),
        tools=commander_tools,
        llm=llm_commander,
        verbose=True,
        max_iter=max_iterations,
    )

    return commander, scout, scribe, quality_validator, product_owner, content_pm, beginner_advocate
