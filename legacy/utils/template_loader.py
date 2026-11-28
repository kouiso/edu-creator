"""
Jinja2テンプレートローダーとレンダリングユーティリティ

参考: 実務プロジェクトのLLMチャットフロー実装
"""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template
from typing import Dict, Any

# テンプレートディレクトリのパス
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "prompts"

# Jinja2環境を初期化
env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    trim_blocks=True,  # ブロックタグ後の改行を削除
    lstrip_blocks=True,  # ブロックタグ前の空白を削除
    autoescape=False,  # HTMLエスケープを無効化（プロンプトはHTMLではない）
)


def load_template(template_name: str) -> Template:
    """
    テンプレートファイルを読み込み
    
    Args:
        template_name: テンプレートファイル名（例: "scribe_system.jinja2"）
    
    Returns:
        Jinja2のTemplateオブジェクト
    
    Example:
        >>> template = load_template("scribe_system.jinja2")
        >>> prompt = template.render(tech_stack="Next.js 15, TypeScript 5")
    """
    return env.get_template(template_name)


def render_template(template_name: str, **context: Any) -> str:
    """
    テンプレートをレンダリングしてプロンプト文字列を生成
    
    Args:
        template_name: テンプレートファイル名
        **context: テンプレートに渡す変数（キーワード引数）
    
    Returns:
        レンダリングされたプロンプト文字列
    
    Example:
        >>> prompt = render_template(
        ...     "scribe_system.jinja2",
        ...     skill_content="<SKILL.mdの内容>",
        ...     tech_stack="Next.js 15, TypeScript 5",
        ...     target_audience="プログラミング初心者",
        ...     learning_objectives="環境構築、基本的なコンポーネント作成"
        ... )
    """
    template = load_template(template_name)
    return template.render(**context)


def get_scribe_system_prompt(
    skill_content: str,
    tech_stack: str = "Next.js 15, TypeScript 5, Prisma, tRPC",
    target_audience: str = "プログラミング初心者（HTML/CSSの基礎知識あり）",
    learning_objectives: str = "Webアプリケーション開発の基礎を習得する",
) -> str:
    """
    Scribeエージェント用のシステムプロンプトを生成
    
    Args:
        skill_content: SKILL.mdの内容（必須）
        tech_stack: 技術スタック
        target_audience: 対象読者
        learning_objectives: 学習目標
    
    Returns:
        システムプロンプト文字列
    """
    return render_template(
        "scribe_system.jinja2",
        skill_content=skill_content,
        tech_stack=tech_stack,
        target_audience=target_audience,
        learning_objectives=learning_objectives,
    )


def get_pm_review_prompt(
    skill_content: str,
    tutorial_json: str,
) -> str:
    """
    PM（Product Manager）レビュー用のシステムプロンプトを生成
    
    Args:
        skill_content: Code Review SKILL.mdの内容
        tutorial_json: レビュー対象のチュートリアル（JSON文字列）
    
    Returns:
        システムプロンプト文字列
    """
    return render_template(
        "pm_review.jinja2",
        skill_content=skill_content,
        tutorial_json=tutorial_json,
    )


# ===== スキルファイル読み込みユーティリティ =====

def load_skill(skill_name: str) -> str:
    """
    スキルファイル（SKILL.md）を読み込む
    
    Args:
        skill_name: スキル名（例: "tutorial-writing", "code-review"）
    
    Returns:
        SKILL.mdの内容
    
    Example:
        >>> tutorial_skill = load_skill("tutorial-writing")
        >>> code_review_skill = load_skill("code-review")
    """
    skill_path = Path(__file__).parent.parent / "skills" / skill_name / "SKILL.md"
    if skill_path.exists():
        return skill_path.read_text(encoding="utf-8")
    else:
        raise FileNotFoundError(f"スキルファイルが見つかりません: {skill_path}")


# ===== 使用例 =====

if __name__ == "__main__":
    # Example 1: Scribeシステムプロンプト生成
    print("=== Example 1: Scribe System Prompt ===")
    skill_content = load_skill("tutorial-writing")
    scribe_prompt = get_scribe_system_prompt(
        skill_content=skill_content,
        tech_stack="Next.js 15, TypeScript 5",
        target_audience="プログラミング初心者",
        learning_objectives="環境構築とコンポーネント作成",
    )
    print(scribe_prompt[:500])  # 最初の500文字を表示
    
    # Example 2: PMレビュープロンプト生成
    print("\n=== Example 2: PM Review Prompt ===")
    code_review_skill = load_skill("code-review")
    tutorial_json = '{"outline": {...}, "sections": [...]}'
    pm_prompt = get_pm_review_prompt(
        skill_content=code_review_skill,
        tutorial_json=tutorial_json,
    )
    print(pm_prompt[:500])  # 最初の500文字を表示
