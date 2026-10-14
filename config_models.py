"""
=============================================================================
🔒 Configuration Models with Pydantic (Type-safe config validation)
=============================================================================
Configuration validation using Pydantic V2 to catch config errors BEFORE AI runs.

Similar to TypeScript's Zod - we use .model_validate() instead of safeParser,
but the concept is the same: strict validation before execution.

このモジュールは、YAMLから読み込んだ設定を型安全に検証します。
AIが動き出す前に、設定のミスを引っかかることができます。
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SafetyConfig(BaseModel):
    """安全設定モデル"""
    model_config = ConfigDict(str_strip_whitespace=True)

    max_iterations: int = Field(default=3, ge=1, le=10)
    """最大イテレーション回数（1-10）"""

    max_retries: int = Field(default=3, ge=1, le=10)
    """最大リトライ回数（1-10）"""

    max_rpm: int = Field(default=10, ge=1, le=100)
    """最大リクエスト/分（1-100）"""

    timeout_seconds: int = Field(default=1800, ge=60, le=7200)
    """タイムアウト秒数（60-7200秒）"""

    cost_confirmation_threshold_usd: float = Field(default=1.0, ge=0.1, le=100.0)
    """コスト確認閾値（0.1-100ドル）"""


class ExclusionsConfig(BaseModel):
    """除外設定モデル"""
    model_config = ConfigDict(str_strip_whitespace=True)

    directories: list[str] = Field(default_factory=list)
    """除外ディレクトリ"""

    patterns: list[str] = Field(default_factory=list)
    """除外ファイルパターン"""


# 有効なエージェント名（バリデーション用）
VALID_AGENT_NAMES = {
    "scout", "scribe", "validator",
    "product_owner", "content_pm", "quality_pm", "beginner_advocate",
    "router",
}


class AgentLLMConfig(BaseModel):
    """
    エージェント個別LLM設定

    使用例:
        agent_models:
          scout:
            model: "gemini-2.0-flash"
            temperature: 0.3
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    model: str = Field(min_length=1)
    """モデル名（例: "gpt-5.2", "gemini-2.0-flash", "claude-3-5-sonnet"）"""

    temperature: float = Field(default=0.4, ge=0.0, le=1.0)
    """温度（0.0-1.0）"""


class LLMConfig(BaseModel):
    """
    LLM設定モデル

    3つのレベルで設定可能:
    1. agent_models[agent_name] - エージェント個別設定（最優先）
    2. commander_model/worker_model - レイヤーデフォルト
    3. 環境変数 - システムデフォルト
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    # ==========================================================================
    # 既存フィールド（後方互換性のため維持）
    # ==========================================================================
    commander_model: str = Field(default="gpt-5.2")
    """指令層モデル（ProductOwner, ContentPM, QualityPM, BeginnerAdvocate）"""

    worker_model: str = Field(default="gemini-2.0-flash")
    """作業層モデル（Scout, Scribe, Validator）"""

    commander_temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    """Commander層の温度（0.0-1.0）"""

    worker_temperature: float = Field(default=0.4, ge=0.0, le=1.0)
    """Worker層の温度（0.0-1.0）"""

    # ==========================================================================
    # 新規フィールド: エージェント個別設定
    # ==========================================================================
    agent_models: dict[str, AgentLLMConfig] | None = Field(default=None)
    """
    エージェント個別LLM設定（オプション）

    キーはエージェント名:
    - scout, scribe, validator (Worker層)
    - product_owner, content_pm, quality_pm, beginner_advocate (Judgment層)
    - router (Routerエージェント)
    """

    # ==========================================================================
    # 新規フィールド: Routerエージェント設定
    # ==========================================================================
    router_model: str | None = Field(default=None)
    """
    Routerエージェント用モデル（オプション）

    設定するとProcess.hierarchicalモードでRouterエージェントが有効化される。
    軽量モデル推奨（例: "gpt-4o-mini"）
    """

    router_temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    """Routerの温度（低めで決定的なルーティング推奨）"""

    @field_validator('agent_models')
    @classmethod
    def validate_agent_names(cls, v: dict[str, AgentLLMConfig] | None) -> dict[str, AgentLLMConfig] | None:
        """エージェント名が有効かどうかを検証"""
        if v is None:
            return v
        invalid_names = set(v.keys()) - VALID_AGENT_NAMES
        if invalid_names:
            raise ValueError(
                f"Invalid agent names: {invalid_names}. "
                f"Valid names: {sorted(VALID_AGENT_NAMES)}"
            )
        return v


class QualityRulesConfig(BaseModel):
    """品質ルール設定モデル"""
    model_config = ConfigDict(str_strip_whitespace=True)

    max_code_lines: int = Field(default=25, ge=10, le=100)
    """コードブロック最大行数（10-100行）"""

    max_paragraph_sentences: int = Field(default=3, ge=2, le=10)
    """段落最大文数（2-10文）"""

    require_filepath: bool = Field(default=True)
    """ファイルパス指定を必須にするか"""

    require_verification: bool = Field(default=True)
    """動作確認セクションを必須にするか"""

    require_metaphor: bool = Field(default=True)
    """メタファーを必須にするか"""

    forbidden_words: list[str] = Field(default_factory=list)
    """禁止ワードリスト"""

    min_tables_per_day: int = Field(default=4, ge=1, le=20)
    """1日あたり最小テーブル数（1-20個）"""

    min_screenshots: int = Field(default=3, ge=1, le=20)
    """最小スクリーンショット数（1-20個）"""


class QualityCheckConfig(BaseModel):
    """品質チェック設定モデル（環境別に切り替え可能）"""
    model_config = ConfigDict(str_strip_whitespace=True)

    min_word_count: int = Field(default=4000, ge=1000, le=20000)
    """最小単語数（1000-20000）"""

    min_code_blocks: int = Field(default=5, ge=1, le=50)
    """最小コードブロック数（1-50）"""

    min_tables: int = Field(default=3, ge=0, le=20)
    """最小テーブル数（0-20）"""

    max_consecutive_code_lines: int = Field(default=20, ge=10, le=100)
    """連続コード最大行数（10-100）"""

    skip_llm_judge: bool = Field(default=False)
    """LLM Judge評価をスキップするか（開発環境でコスト削減）"""

    skip_mechanical_check: bool = Field(default=False)
    """機械的品質チェックをスキップするか"""


class DebugConfig(BaseModel):
    """デバッグ設定モデル"""
    model_config = ConfigDict(str_strip_whitespace=True)

    verbose_logging: bool = Field(default=False)
    """詳細ログを出力するか"""

    save_intermediate_outputs: bool = Field(default=True)
    """中間出力を保存するか"""

    print_token_usage: bool = Field(default=False)
    """トークン使用量を表示するか"""


class ChapterConfig(BaseModel):
    """章の設定モデル"""
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    """章ID（例：day01）"""

    title: str = Field(min_length=1)
    """章タイトル"""

    subtitle: str = Field(default="")
    """副タイトル（オプション）"""

    topics: list[str] = Field(default_factory=list)
    """トピック一覧"""

    @field_validator('id')
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        """IDフォーマットを検証（day01, day02等）"""
        if not v or len(v) < 2:
            raise ValueError(f"ID must be at least 2 characters: {v}")
        return v


class TeachingConfig(BaseModel):
    """教育方法設定モデル"""
    model_config = ConfigDict(str_strip_whitespace=True)

    philosophy: str = Field(default="")
    """教育哲学"""

    guidelines: list[str] = Field(default_factory=list)
    """ガイドライン"""

    terminology_rules: list[str] = Field(default_factory=list)
    """専門用語ルール"""


class EduConfig(BaseModel):
    """
    メイン設定モデル（edu-config.yamlの構造を完全にモデル化）

    使用方法：
        from config_models import EduConfig

        # YAMLから読み込む
        import yaml
        with open('edu-config.yaml') as f:
            config_dict = yaml.safe_load(f)

        # Pydanticで検証
        try:
            config = EduConfig.model_validate(config_dict)
            print("✅ Config is valid!")
        except ValidationError as e:
            print(f"❌ Config validation failed: {e}")
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    """安全設定"""

    exclusions: ExclusionsConfig = Field(default_factory=ExclusionsConfig)
    """除外設定"""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    """LLM設定"""

    quality_rules: QualityRulesConfig = Field(default_factory=QualityRulesConfig)
    """品質ルール"""

    quality: QualityCheckConfig = Field(default_factory=QualityCheckConfig)
    """品質チェック設定（環境別）"""

    debug: DebugConfig = Field(default_factory=DebugConfig)
    """デバッグ設定"""

    teaching: TeachingConfig = Field(default_factory=TeachingConfig)
    """教育方法設定"""

    chapters: list[ChapterConfig] = Field(default_factory=list)
    """章リスト"""

    log_dir: str = Field(default="logs")
    """ログディレクトリ"""

    log_level: str = Field(default="INFO")
    """ログレベル（DEBUG, INFO, WARNING, ERROR）"""

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """ログレベルを検証"""
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR'}
        if v not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}, got: {v}")
        return v

    @field_validator('chapters')
    @classmethod
    def validate_chapters_not_empty(cls, v: list[ChapterConfig]) -> list[ChapterConfig]:
        """章リストが空でないことを確認"""
        if not v:
            raise ValueError("chapters list cannot be empty")
        return v


class OutlineOutput(BaseModel):
    """
    AIが生成したアウトラインのモデル（Scoutから出力される）

    使用方法：
        # AIからのアウトライン出力をJSONで得る
        outline_json = scout_result  # JSONフォーマット

        try:
            outline = OutlineOutput.model_validate_json(outline_json)
            print(f"✅ Outline valid: {outline.title}")
        except ValidationError as e:
            print(f"❌ Outline validation failed: {e}")
            # AIにエラーを返す
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=5)
    """アウトラインタイトル（最小5文字）"""

    description: str = Field(min_length=10)
    """説明（最小10文字）"""

    key_concepts: list[str] = Field(min_items=2, max_items=10)
    """主要概念（2-10個）"""

    learning_outcomes: list[str] = Field(min_items=1, max_items=5)
    """学習成果（1-5個）"""

    estimated_time_minutes: int = Field(ge=15, le=180)
    """推定時間（15-180分）"""

    prerequisite_knowledge: list[str] = Field(default_factory=list)
    """前提知識"""


class ValidationError(Exception):
    """設定検証エラー"""
    pass


def validate_config(config_dict: dict[str, Any]) -> tuple[bool, EduConfig | None, str]:
    """
    設定をPydanticで検証する（Zod的な安全な検証）

    Args:
        config_dict: YAMLから読み込んだ辞書

    Returns:
        (成功フラグ, 設定オブジェクト or None, エラーメッセージ)
    """
    try:
        config = EduConfig.model_validate(config_dict)
        return True, config, ""
    except Exception as e:
        error_msg = f"❌ Config validation failed:\n{e}"
        return False, None, error_msg


def validate_outline(outline_json: str) -> tuple[bool, OutlineOutput | None, str]:
    """
    AIが生成したアウトラインをJSONで検証する

    Args:
        outline_json: JSONフォーマットの文字列

    Returns:
        (成功フラグ, アウトラインオブジェクト or None, エラーメッセージ)
    """
    try:
        outline = OutlineOutput.model_validate_json(outline_json)
        return True, outline, ""
    except Exception as e:
        error_msg = f"❌ Outline validation failed:\n{e}"
        return False, None, error_msg
