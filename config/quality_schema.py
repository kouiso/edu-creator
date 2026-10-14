"""
=============================================================================
品質スキーマ（Quality Schema）
プロンプトとチェッカーの一元管理

目的:
- プロンプト（prompt/task/write.py）と品質チェッカー（quality_checker.py）の
  ルールを一箇所で定義し、同期を保つ
- 設定変更時の手間を削減

使用方法:
1. quality_checker.py: このスキーマを読み込んで検査
2. prompt/task/write.py: このスキーマをプロンプトに埋め込む
=============================================================================
"""

from typing import Any

# =============================================================================
# 品質スキーマ定義（JSON Schema風）
# =============================================================================

QUALITY_SCHEMA: dict[str, Any] = {
    # 必須セクション定義
    "required_sections": {
        "problem_statement": {
            "patterns": [
                "事前チェック",
                "このDayでやること",
                "このDayについて",
                "🤔",
                "問題点",
                "悩み",
                "なぜ",
            ],
            "min_count": 1,
            "description": "読者の問題意識・疑問を引き出すセクション",
        },
        "metaphor_explanation": {
            "patterns": [
                "今日学ぶこと",
                "例え話",
                "メタファー",
                "💡",
                "解決策",
                "説明",
                "理解する",
            ],
            "min_count": 1,
            "description": "概念をメタファーで説明するセクション",
        },
        "step_by_step": {
            "patterns": ["ステップ", "Step", "手順"],
            "min_count": 3,
            "description": "具体的な実行手順",
        },
        "verification": {
            "patterns": ["動作確認", "確認方法", "確認できます", "確認ポイント"],
            "min_count": 1,
            "description": "動作確認セクション",
        },
        "error_handling": {
            "patterns": [
                "トラブルシューティング",
                "エラー",
                "問題",
                "失敗",
                "つまずき",
                "救済",
            ],
            "min_count": 1,
            "description": "エラー対処セクション",
        },
    },
    # 禁止ワード（AIの手抜き検出）
    "forbidden_words": [
        "同様に",
        "同じように",
        "同じ方法で",
        "残りも",
        "その他も",
        "以下も",
        "以下略",
        "省略",
        "簡単です",
        "すぐできます",
        "簡単に",
        "おなじ",
        "一緒",
    ],
    # コードブロック関連
    "code_blocks": {
        "min_count": 3,
        "max_lines_per_block": 25,
        "require_filepath_comment": True,
        "require_explanation_after": True,
    },
    # テーブル関連
    "tables": {
        "min_count": 4,
        "require_complete": True,  # ヘッダー+セパレーター+データ行が必須
    },
    # Mermaid図関連
    "mermaid": {
        "min_count": 1,
    },
    # 段落関連
    "paragraphs": {
        "max_sentences": 3,
    },
    # 文の長さ
    "sentences": {
        "max_length": 80,
        "warning_threshold": 5,  # 80文字超の文が5個以上で警告
    },
    # 専門用語ルール
    "terminology": {
        "require_explanation_on_first_use": True,
        "format": "用語（読み方：意味）",
        "common_terms": [
            {"term": "Node.js", "reading": "ノードジェイエス"},
            {"term": "npm", "reading": "エヌピーエム"},
            {"term": "Docker", "reading": "ドッカー"},
            {"term": "PostgreSQL", "reading": "ポストグレス"},
            {"term": "Taskfile", "reading": "タスクファイル"},
            {"term": "Prisma", "reading": "プリズマ"},
            {"term": "Next.js", "reading": "ネクストジェイエス"},
            {"term": "API", "reading": "エーピーアイ"},
        ],
    },
    # 絵文字使用ルール
    "emoji": {
        "allowed": False,  # 絵文字は使用しない
    },
    # 文体
    "style": {
        "required": "です・ます調",
        "forbidden": ["だ・である調", "ですます体の混在"],
    },
}


# =============================================================================
# プロンプト生成用ヘルパー
# =============================================================================


def generate_quality_rules_text() -> str:
    """
    品質ルールをプロンプト用のテキストに変換

    Returns:
        str: プロンプトに埋め込む品質ルール文字列
    """
    schema = QUALITY_SCHEMA

    rules_text = "=== QUALITY RULES (品質ルール) ===\n\n"

    # 禁止ワード
    rules_text += "【絶対禁止ワード】\n"
    rules_text += "以下の表現は「手抜き」として検出されます：\n"
    for word in schema["forbidden_words"]:
        rules_text += f"  ❌ 「{word}」\n"
    rules_text += "\n"

    # コードブロック
    rules_text += "【コードブロックルール】\n"
    rules_text += f"- 最大{schema['code_blocks']['max_lines_per_block']}行まで\n"
    rules_text += f"- 最低{schema['code_blocks']['min_count']}個以上必要\n"
    rules_text += "- 全コードブロックに `// filepath: path/to/file` コメント必須\n"
    rules_text += "- コードブロック直後に日本語説明必須\n\n"

    # テーブル
    rules_text += "【テーブルルール】\n"
    rules_text += f"- 最低{schema['tables']['min_count']}個以上必要\n"
    rules_text += "- ヘッダー行 + セパレーター行 + データ行が完全に揃っていること\n\n"

    # Mermaid図
    rules_text += "【Mermaid図ルール】\n"
    rules_text += f"- 最低{schema['mermaid']['min_count']}個以上必要\n"
    rules_text += "- アーキテクチャやフロー図に使用\n\n"

    # 段落
    rules_text += "【段落ルール】\n"
    rules_text += f"- 1段落あたり最大{schema['paragraphs']['max_sentences']}文まで\n"
    rules_text += "- 4文以上になる場合は段落を分割\n\n"

    # 専門用語
    rules_text += "【専門用語ルール】\n"
    rules_text += f"- 初出時のフォーマット: {schema['terminology']['format']}\n"
    rules_text += "- 例: Docker（ドッカー：アプリを箱詰めして動かす仕組み）\n"
    rules_text += "- 2回目以降は説明なしで使用可能\n\n"

    # 必須セクション
    rules_text += "【必須セクション】\n"
    for section_key, section_info in schema["required_sections"].items():
        patterns_str = "、".join(section_info["patterns"][:3])
        rules_text += f"- {section_info['description']}: 「{patterns_str}」等のいずれかを含む\n"
    rules_text += "\n"

    return rules_text


# =============================================================================
# 検証用ヘルパー（quality_checker.py から使用）
# =============================================================================


def get_required_section_patterns() -> list[tuple[str, str]]:
    """
    必須セクションのパターンリストを取得

    Returns:
        list[tuple[str, str]]: (正規表現パターン, 説明) のリスト
    """
    schema = QUALITY_SCHEMA
    patterns = []

    for section_key, section_info in schema["required_sections"].items():
        # パターンを | で結合して正規表現に
        pattern = "|".join(section_info["patterns"])
        description = section_info["description"]
        patterns.append((pattern, description))

    return patterns


def get_forbidden_words() -> list[str]:
    """禁止ワードのリストを取得"""
    return QUALITY_SCHEMA["forbidden_words"]


def get_code_block_limits() -> dict[str, Any]:
    """コードブロック制約を取得"""
    return QUALITY_SCHEMA["code_blocks"]


def get_table_limits() -> dict[str, Any]:
    """テーブル制約を取得"""
    return QUALITY_SCHEMA["tables"]


def get_mermaid_limits() -> dict[str, Any]:
    """Mermaid制約を取得"""
    return QUALITY_SCHEMA["mermaid"]
