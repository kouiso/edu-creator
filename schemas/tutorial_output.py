"""
構造化出力用のPydanticスキーマ定義

OpenAI Structured Outputを使用して、LLMの出力を型安全に管理します。
"""
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from enum import Enum


class SectionType(str, Enum):
    """セクションタイプの列挙型"""
    INTRODUCTION = "introduction"  # 導入セクション
    EXPLANATION = "explanation"    # 説明セクション
    CODE_EXAMPLE = "code_example"  # コード例セクション
    EXERCISE = "exercise"          # 演習セクション
    SUMMARY = "summary"            # まとめセクション


class CodeBlock(BaseModel):
    """コードブロックの構造"""
    filepath: str = Field(
        description="ファイルパス（例: src/components/Button.tsx）"
    )
    language: str = Field(
        description="プログラミング言語（例: typescript, python, bash）"
    )
    code: str = Field(
        description="コード本体（25行以内）"
    )
    explanation: str = Field(
        description="コードの説明（何をしているか、なぜ必要か）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "filepath": "src/components/Button.tsx",
                "language": "typescript",
                "code": 'export const Button = () => <button>Click</button>;',
                "explanation": "ボタンコンポーネントを作成します。クリック可能なUI要素を提供します。"
            }
        }


class Screenshot(BaseModel):
    """スクリーンショットの構造"""
    filename: str = Field(
        description="スクリーンショットのファイル名（例: day01-step01.png）"
    )
    alt_text: str = Field(
        description="代替テキスト（画像の内容を説明）"
    )
    caption: str = Field(
        description="キャプション（画像の補足説明）"
    )


class ErrorHandling(BaseModel):
    """エラーハンドリングの構造"""
    error_message: str = Field(
        description="エラーメッセージ（実際に表示される文言）"
    )
    cause: str = Field(
        description="エラーの原因（なぜこのエラーが出るか）"
    )
    solution: str = Field(
        description="解決策（具体的な修正方法）"
    )


class TutorialSection(BaseModel):
    """チュートリアルセクションの構造"""
    section_type: SectionType = Field(
        description="セクションのタイプ"
    )
    title: str = Field(
        description="セクションタイトル（絵文字 + タイトル）"
    )
    content: str = Field(
        description="セクションの本文（Markdown形式、段落は3文以内）"
    )
    code_blocks: List[CodeBlock] = Field(
        default_factory=list,
        description="コードブロックのリスト"
    )
    screenshots: List[Screenshot] = Field(
        default_factory=list,
        description="スクリーンショットのリスト"
    )
    error_handling: List[ErrorHandling] = Field(
        default_factory=list,
        description="エラーハンドリングのリスト"
    )
    key_points: List[str] = Field(
        default_factory=list,
        description="このセクションで学ぶポイント（箇条書き）"
    )


class ChapterOutline(BaseModel):
    """章のアウトライン（Commander/ContentPMが作成）"""
    chapter_number: int = Field(
        description="章番号（例: 1）"
    )
    title: str = Field(
        description="章のタイトル（例: 環境構築）"
    )
    learning_objectives: List[str] = Field(
        description="学習目標（この章で学ぶこと）"
    )
    sections: List[str] = Field(
        description="セクションリスト（セクションタイトルの配列）"
    )
    estimated_time: int = Field(
        description="推定学習時間（分）"
    )
    prerequisites: List[str] = Field(
        default_factory=list,
        description="前提知識（この章を学ぶ前に必要な知識）"
    )


class TutorialChapter(BaseModel):
    """完成したチュートリアル章（Scribeが作成）"""
    outline: ChapterOutline = Field(
        description="章のアウトライン"
    )
    sections: List[TutorialSection] = Field(
        description="セクションのリスト"
    )


class ReviewIssue(BaseModel):
    """レビュー時の指摘事項"""
    severity: Literal["critical", "major", "minor"] = Field(
        description="重要度（critical: 必須修正, major: 推奨修正, minor: 余裕があれば）"
    )
    location: str = Field(
        description="問題箇所（セクション名、行番号など）"
    )
    problem: str = Field(
        description="問題内容（何が問題か）"
    )
    reason: str = Field(
        description="理由（なぜ問題か）"
    )
    suggestion: str = Field(
        description="修正案（具体的にどう修正するか）"
    )


class ReviewResult(BaseModel):
    """レビュー結果（PM/QualityPM/BeginnerAdvocateが作成）"""
    approval: bool = Field(
        description="承認するか（True: 承認, False: 修正が必要）"
    )
    reviewer: str = Field(
        description="レビュワー名（ContentPM, QualityPM, BeginnerAdvocate, ProductOwner）"
    )
    review_comment: str = Field(
        description="総合コメント"
    )
    good_points: List[str] = Field(
        default_factory=list,
        description="良かった点"
    )
    issues: List[ReviewIssue] = Field(
        default_factory=list,
        description="指摘事項（修正が必要な箇所）"
    )


# ===== 多段階選択パターン用のモデル =====

class FirstStageDecision(BaseModel):
    """第1段階: 何をするかを決定"""
    action: Literal["create_new_section", "modify_existing", "skip"] = Field(
        description="実行するアクション"
    )
    reason: str = Field(
        description="この判断をした理由"
    )


class SecondStageDecision(BaseModel):
    """第2段階: どのセクションを対象にするか"""
    target_section_index: int = Field(
        description="対象セクションのインデックス（0始まり）"
    )
    section_type: SectionType = Field(
        description="セクションタイプ"
    )


class ThirdStageDecision(BaseModel):
    """第3段階: 具体的な内容を生成"""
    section: TutorialSection = Field(
        description="生成されたセクション"
    )


# ===== 差分ベース更新用のモデル =====

class TutorialDiff(BaseModel):
    """チュートリアルの差分更新"""
    path: str = Field(
        description="更新対象のJSONPath（例: sections[0].title）"
    )
    operation: Literal["add", "replace", "delete"] = Field(
        description="操作タイプ"
    )
    value: Optional[str] = Field(
        default=None,
        description="新しい値（deleteの場合はNone）"
    )
    reason: str = Field(
        description="この変更を行う理由"
    )


class DiffBasedUpdate(BaseModel):
    """差分ベースの更新リクエスト"""
    diffs: List[TutorialDiff] = Field(
        description="適用する差分のリスト"
    )
    summary: str = Field(
        description="更新内容のサマリー"
    )
