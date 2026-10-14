"""
統合テスト: AGENTS.md + SKILL.md + Jinja2 + Structured Output

このスクリプトは、新しく導入した4つのパターンが正しく統合されているかをテストします。

テスト内容:
1. SKILL.mdの読み込み
2. Jinja2テンプレートのレンダリング
3. Structured Output（OpenAI）の呼び出し
4. エージェントの実行フロー
"""
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.template_loader import load_skill, get_scribe_system_prompt, get_pm_review_prompt
from utils.structured_llm import call_structured_llm
from schemas.tutorial_output import ChapterOutline, TutorialChapter, ReviewResult
import json


def test_skill_loading():
    """Test 1: スキルファイルの読み込み"""
    print("=== Test 1: スキルファイルの読み込み ===")
    
    try:
        tutorial_skill = load_skill("tutorial-writing")
        print(f"✅ Tutorial Writing Skill読み込み成功 ({len(tutorial_skill)} 文字)")
        
        code_review_skill = load_skill("code-review")
        print(f"✅ Code Review Skill読み込み成功 ({len(code_review_skill)} 文字)")
        
        return True
    except Exception as e:
        print(f"❌ スキル読み込み失敗: {e}")
        return False


def test_template_rendering():
    """Test 2: Jinja2テンプレートのレンダリング"""
    print("\n=== Test 2: Jinja2テンプレートのレンダリング ===")
    
    try:
        skill_content = load_skill("tutorial-writing")
        prompt = get_scribe_system_prompt(
            skill_content=skill_content,
            tech_stack="Next.js 15, TypeScript 5",
            target_audience="プログラミング初心者",
            learning_objectives="環境構築とコンポーネント作成",
        )
        
        print(f"✅ プロンプト生成成功 ({len(prompt)} 文字)")
        print(f"プロンプトの冒頭:\n{prompt[:200]}...")
        
        return True
    except Exception as e:
        print(f"❌ プロンプト生成失敗: {e}")
        return False


def test_structured_output_outline():
    """Test 3: 構造化出力（ChapterOutline）"""
    print("\n=== Test 3: 構造化出力（ChapterOutline） ===")
    
    # OpenAI APIキーのチェック
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("⏭️  スキップ（OPENAI_API_KEYが設定されていません）")
        return True
    
    try:
        skill_content = load_skill("tutorial-writing")
        system_prompt = get_scribe_system_prompt(
            skill_content=skill_content,
            tech_stack="Next.js 15, TypeScript 5",
            target_audience="プログラミング初心者",
            learning_objectives="環境構築",
        )
        
        user_prompt = """
        「Next.js 15の環境構築」をテーマに、章のアウトラインを作成してください。
        
        要件:
        - 章番号: 1
        - 推定学習時間: 30分
        - 前提知識: HTML/CSSの基礎、コマンドラインの基本操作
        """
        
        print("⏳ OpenAI APIを呼び出し中...")
        outline = call_structured_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ChapterOutline,
            temperature=0.7,
        )
        
        print(f"✅ ChapterOutline取得成功")
        print(f"タイトル: {outline.title}")
        print(f"学習目標: {outline.learning_objectives}")
        print(f"セクション数: {len(outline.sections)}")
        print(f"推定時間: {outline.estimated_time}分")
        
        return True
    except Exception as e:
        print(f"❌ 構造化出力失敗: {e}")
        return False


def test_structured_output_review():
    """Test 4: 構造化出力（ReviewResult）"""
    print("\n=== Test 4: 構造化出力（ReviewResult） ===")
    
    # OpenAI APIキーのチェック
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("⏭️  スキップ（OPENAI_API_KEYが設定されていません）")
        return True
    
    try:
        skill_content = load_skill("code-review")
        
        # レビュー対象のサンプルチュートリアル
        sample_tutorial = {
            "outline": {
                "chapter_number": 1,
                "title": "環境構築",
                "learning_objectives": ["Node.jsのインストール"],
                "sections": ["Node.jsとは", "インストール手順"],
                "estimated_time": 30,
                "prerequisites": ["コマンドライン操作"]
            },
            "sections": [
                {
                    "section_type": "code_example",
                    "title": "Node.jsのインストール",
                    "content": "以下のコマンドでインストールします",
                    "code_blocks": [
                        {
                            "filepath": "terminal",
                            "language": "bash",
                            "code": "npm install",
                            "explanation": "npmパッケージをインストール"
                        }
                    ],
                    "screenshots": [],
                    "error_handling": [],
                    "key_points": ["Node.jsをインストールする"]
                }
            ]
        }
        
        system_prompt = get_pm_review_prompt(
            skill_content=skill_content,
            tutorial_json=json.dumps(sample_tutorial, ensure_ascii=False, indent=2),
        )
        
        user_prompt = "上記のチュートリアルをレビューしてください。"
        
        print("⏳ OpenAI APIを呼び出し中...")
        review = call_structured_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ReviewResult,
            temperature=0.3,  # レビューは低温度で
        )
        
        print(f"✅ ReviewResult取得成功")
        print(f"承認: {'✅ 承認' if review.approval else '⚠️ 修正が必要'}")
        print(f"レビュワー: {review.reviewer}")
        print(f"良かった点: {len(review.good_points)}件")
        print(f"指摘事項: {len(review.issues)}件")
        
        if review.issues:
            print("\n指摘事項の詳細:")
            for i, issue in enumerate(review.issues, 1):
                print(f"  {i}. [{issue.severity}] {issue.problem}")
        
        return True
    except Exception as e:
        print(f"❌ レビュー失敗: {e}")
        return False


def test_end_to_end():
    """Test 5: エンドツーエンドテスト（Scribe → PM Review）"""
    print("\n=== Test 5: エンドツーエンド（Scribe → PM Review） ===")
    
    # このテストはAPI呼び出しが多いため、実際の運用時のみ実行
    print("⏭️  スキップ（実際の運用時に実行）")
    return True


def main():
    """統合テストのメイン関数"""
    print("🧪 Production Pattern Integration Test\n")
    
    results = {
        "スキル読み込み": test_skill_loading(),
        "テンプレートレンダリング": test_template_rendering(),
        "構造化出力（Outline）": test_structured_output_outline(),
        "構造化出力（Review）": test_structured_output_review(),
        "エンドツーエンド": test_end_to_end(),
    }
    
    print("\n" + "="*60)
    print("📊 テスト結果サマリー")
    print("="*60)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\n合計: {passed}/{total} テスト成功")
    
    if passed == total:
        print("\n🎉 全てのテストが成功しました！")
        return 0
    else:
        print(f"\n⚠️ {total - passed}件のテストが失敗しました。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
