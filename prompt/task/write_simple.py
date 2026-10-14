"""
=============================================================================
Write Task Prompts - SIMPLIFIED VERSION (100行以下)
執筆タスクプロンプト - 簡素化バージョン

設計思想:
- 絶対守るべきルールだけをプロンプトに含める
- 詳細なルールは検証スクリプトで強制する
- AIが「全てを守ろうとして何も守れない」状態を避ける
=============================================================================
"""

# =============================================================================
# 簡素化プロンプト（100行以下）
# =============================================================================

WRITE_TASK_SIMPLE: str = """
あなたは初心者向けプログラミングチュートリアルの執筆者です。
日本語（です・ます調）で執筆してください。

【執筆する章】
{chapter_title} {chapter_subtitle}

【5つの絶対ルール】
以下のルールを必ず守ってください。これらは自動スクリプトでチェックされます。

1. コードブロックは25行以下
   - 超える場合は機能単位で分割し、間に説明文を入れる

2. 表を4個以上、Mermaid図を1個以上含める
   - 表: 比較、コマンド一覧、トラブルシューティング等に使用
   - Mermaid: アーキテクチャや処理フロー図に使用

3. コードブロックには必ず filepath: コメントを入れる
   ```typescript
   // filepath: src/app/page.tsx
   export default function Page() {{ ... }}
   ```

4. 「パート1/2」形式の分割は禁止
   - 代わりに機能単位で分割: インポート部、型定義部、本体部 等

5. shadcn/ui + Tailwind CSS を使用（MUI禁止）
   - Button は @/components/ui/button から
   - スタイルは className="..." で

【アウトライン】
{outline}

【調査結果】
{research_results}

【出力形式】
以下の構造で出力してください:

# タイトル

## はじめに
（読者の課題と、この章で学ぶこと）

## Step 1: ...
（各ステップには所要時間を明記: 例「15分」）

## Step N: ...

## まとめ
（チェックリスト形式で完了確認）

## 次回予告

---

ターゲット文字数: 4,000-6,000文字
"""


WRITE_EXPECTED_OUTPUT_SIMPLE: str = """
日本語チュートリアル（です・ます調）
- 4,000-6,000文字
- 表4個以上
- Mermaid図1個以上
- コードブロック25行以下
- filepath:コメント付き
"""


# =============================================================================
# 品質フィードバック付きプロンプト（再生成時に使用）
# =============================================================================

WRITE_TASK_WITH_FEEDBACK: str = """
あなたは初心者向けプログラミングチュートリアルの執筆者です。
日本語（です・ます調）で執筆してください。

【執筆する章】
{chapter_title} {chapter_subtitle}

【前回の品質チェック結果 - 必ず修正してください】
{quality_feedback}

【5つの絶対ルール】
1. コードブロックは25行以下
2. 表を4個以上、Mermaid図を1個以上
3. filepath: コメント必須
4. 「パート1/2」分割禁止
5. shadcn/ui使用（MUI禁止）

【アウトライン】
{outline}

【調査結果】
{research_results}

ターゲット文字数: 4,000-6,000文字
"""


# =============================================================================
# ヘルパー関数
# =============================================================================

def get_simple_prompt(
    chapter_title: str,
    chapter_subtitle: str,
    outline: str,
    research_results: str,
) -> str:
    """簡素化プロンプトを生成"""
    return WRITE_TASK_SIMPLE.format(
        chapter_title=chapter_title,
        chapter_subtitle=chapter_subtitle,
        outline=outline,
        research_results=research_results,
    )


def get_prompt_with_feedback(
    chapter_title: str,
    chapter_subtitle: str,
    outline: str,
    research_results: str,
    quality_feedback: str,
) -> str:
    """品質フィードバック付きプロンプトを生成（再生成時）"""
    return WRITE_TASK_WITH_FEEDBACK.format(
        chapter_title=chapter_title,
        chapter_subtitle=chapter_subtitle,
        outline=outline,
        research_results=research_results,
        quality_feedback=quality_feedback,
    )
