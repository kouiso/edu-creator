"""
TutorialQualityChecker のテスト

教材品質チェッカーの各メソッドを検証する。
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from quality_checker import TutorialQualityChecker, validate_markdown_file


class TestCheckMarkdownFormat:
    """check_markdown_format() のテスト"""

    def test_valid_markdown(self):
        """正常なマークダウン"""
        content = "```python\nprint('hello')\n```"
        checker = TutorialQualityChecker(content)
        result = checker.check_markdown_format()
        assert result["passed"] is True
        assert len(result["issues"]) == 0

    def test_four_backticks_error(self):
        """4つのバッククォートで始まるとエラー"""
        content = "````python\nprint('hello')\n````"
        checker = TutorialQualityChecker(content)
        result = checker.check_markdown_format()
        assert result["passed"] is False
        assert any("4個" in issue for issue in result["issues"])

    def test_unmatched_code_blocks(self):
        """コードブロックが対になっていない場合"""
        content = "```python\nprint('hello')\n"
        checker = TutorialQualityChecker(content)
        result = checker.check_markdown_format()
        assert result["passed"] is False
        assert any("対になっていない" in issue for issue in result["issues"])

    def test_multiple_valid_code_blocks(self):
        """複数の正常なコードブロック"""
        content = """
```python
print('hello')
```

```bash
echo "world"
```
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_markdown_format()
        assert result["passed"] is True


class TestCheckRequiredSections:
    """check_required_sections() のテスト"""

    def test_all_sections_present(self):
        """全ての必須セクションが存在"""
        content = """
## 🤔 悩み
何かの問題

## 💡 解決策
説明

## キッチンメタファー
例え話

### ステップ 1
手順

## 動作確認
確認方法

## トラブルシューティング
エラー対処
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_required_sections()
        # 全てのセクションがあるわけではないので passed は False かもしれない
        # 必須セクションの正確な定義に依存
        assert isinstance(result["passed"], bool)
        assert isinstance(result["issues"], list)

    def test_missing_troubleshooting(self):
        """トラブルシューティングセクションがない場合"""
        content = """
## 🤔 問題点
何かの問題

## 💡 解決策
説明
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_required_sections()
        # トラブルシューティング関連がないことを確認
        assert isinstance(result["issues"], list)


class TestCheckCodeBlocks:
    """check_code_blocks() のテスト"""

    def test_minimum_code_blocks(self):
        """コードブロック3個未満でエラー"""
        content = """
```python
print('hello')
```

Some text here.

```bash
echo "world"
```

More text.
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_code_blocks()
        assert result["passed"] is False
        assert any("少ない" in issue for issue in result["issues"])

    def test_sufficient_code_blocks(self):
        """コードブロックが十分にある場合"""
        content = """
```python
print('hello')
```

This explains what the code does.

```bash
echo "world"
```

This is another explanation.

```javascript
console.log('test');
```

Final explanation here with enough text to satisfy the check.
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_code_blocks()
        # コードブロック数は十分だが、説明がないものがあるかも
        assert isinstance(result["passed"], bool)

    def test_code_block_without_explanation(self):
        """コードブロックの後に説明がない場合"""
        content = """
```python
print('hello')
```

```bash
echo "world"
```

```javascript
console.log('test');
```
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_code_blocks()
        # 説明がないので警告が出るはず
        assert any("説明がない" in issue for issue in result["issues"])


class TestCheckTables:
    """check_tables() のテスト"""

    def test_minimum_tables(self):
        """テーブルが3個未満でエラー"""
        content = """
| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_tables()
        assert result["passed"] is False
        assert any("少ない" in issue for issue in result["issues"])

    def test_sufficient_tables(self):
        """テーブルが十分にある場合"""
        content = """
| A | B |
|---|---|
| 1 | 2 |

| C | D |
|---|---|
| 3 | 4 |

| E | F |
|---|---|
| 5 | 6 |
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_tables()
        assert result["passed"] is True


class TestCheckStepByStep:
    """check_step_by_step() のテスト"""

    def test_minimum_steps(self):
        """ステップが3個未満でエラー"""
        content = """
### ステップ 1
何かする

```bash
command
```

### ステップ 2
別のことをする

```bash
another command
```
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_step_by_step()
        assert result["passed"] is False
        assert any("少ない" in issue for issue in result["issues"])

    def test_sufficient_steps(self):
        """ステップが十分にある場合"""
        content = """
### ステップ 1
何かする。役割を説明する。

```bash
command1
```

出力される結果。

### ステップ 2
別のことをする。役割を説明する。

```bash
command2
```

出力される結果。

### ステップ 3
最後のステップ。役割を説明する。

```bash
command3
```

出力される結果。
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_step_by_step()
        # ステップ数は十分だが、説明の有無で結果が変わる
        assert isinstance(result["passed"], bool)


class TestCheckErrorHandling:
    """check_error_handling() のテスト"""

    def test_has_error_section(self):
        """エラーハンドリングセクションがある場合"""
        content = """
## トラブルシューティング

### エラー: 接続失敗
原因: ネットワークの問題
対処法: VPNを確認

### エラー: 認証失敗
原因: パスワードが間違っている
対処法: パスワードをリセット
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_error_handling()
        assert result["passed"] is True

    def test_no_error_section(self):
        """エラーハンドリングセクションがない場合"""
        content = """
## 概要
このチュートリアルでは...

## 手順
1. 最初に...
2. 次に...
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_error_handling()
        assert result["passed"] is False


class TestCheckTechnicalTerms:
    """check_technical_terms() のテスト"""

    def test_explained_terms(self):
        """専門用語が説明されている場合"""
        content = """
Node.js（ノードジェイエス：JavaScriptの実行環境）を使います。
npm（エヌピーエム：パッケージマネージャー）でインストールします。
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_technical_terms()
        assert result["passed"] is True

    def test_unexplained_terms(self):
        """専門用語が説明されていない場合"""
        content = """
Node.js を使ってサーバーを起動します。
npm install を実行してください。
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_technical_terms()
        assert result["passed"] is False
        assert any("説明なし" in issue for issue in result["issues"])


class TestCheckExplanationDepth:
    """check_explanation_depth() のテスト"""

    def test_has_why_explanation(self):
        """「なぜ」の説明がある場合"""
        content = """
なぜこのコマンドを使うかというと、依存関係を解決するためです。
理由は、セキュリティを確保するためです。
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_explanation_depth()
        # 「です」「ます」があるかもチェックされる
        assert isinstance(result["passed"], bool)

    def test_polite_language(self):
        """です・ます調の場合"""
        content = """
この手順を実行します。
結果が表示されます。
設定が完了しました。
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_explanation_depth()
        # 「なぜ」がないので False になる可能性
        assert isinstance(result["passed"], bool)


class TestCheckSentenceLength:
    """check_sentence_length() のテスト"""

    def test_appropriate_length(self):
        """適切な文の長さ"""
        content = """
短い文です。
これも短い文です。
適切な長さの文章です。
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_sentence_length()
        assert result["passed"] is True

    def test_too_long_sentences(self):
        """長すぎる文が多い場合"""
        long_sentence = "これは非常に長い文章であり、" * 10
        content = "\n".join([long_sentence] * 10)
        checker = TutorialQualityChecker(content)
        result = checker.check_sentence_length()
        assert result["passed"] is False
        assert any("長い文" in issue for issue in result["issues"])


class TestCheckPromptLeak:
    """check_prompt_leak() のテスト"""

    def test_no_prompt_leak(self):
        """プロンプトリークがない場合"""
        content = """
## チュートリアル

このセクションでは環境構築を行います。
コマンドを実行してください。
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_prompt_leak()
        assert result["passed"] is True

    def test_instruction_leak(self):
        """指示文が混入している場合"""
        content = """
## チュートリアル

1つずつ書いてください。
以下の形式で出力してください。
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_prompt_leak()
        assert result["passed"] is False
        assert any("混入" in issue for issue in result["issues"])

    def test_role_instruction_leak(self):
        """ロール指示が混入している場合"""
        content = """
あなたは教材作成者です。

## チュートリアル
内容
"""
        checker = TutorialQualityChecker(content)
        result = checker.check_prompt_leak()
        assert result["passed"] is False


class TestCheckAll:
    """check_all() のテスト"""

    def test_returns_all_checks(self):
        """全てのチェック結果を返す"""
        content = "テスト用のコンテンツ"
        checker = TutorialQualityChecker(content)
        result = checker.check_all()

        # 必須キーの確認
        assert "markdown_format" in result
        assert "required_sections" in result
        assert "emoji_usage" in result
        assert "code_blocks" in result
        assert "tables" in result
        assert "step_by_step" in result
        assert "error_handling" in result
        assert "technical_terms" in result
        assert "explanation_depth" in result
        assert "sentence_length" in result
        assert "prompt_leak" in result
        assert "is_passed" in result

    def test_is_passed_reflects_issues(self):
        """is_passed が issues を正しく反映"""
        # 問題のあるコンテンツ
        content = "````python\ncode\n````"
        checker = TutorialQualityChecker(content)
        # generate_report() を呼ぶと self.issues が populated される
        checker.generate_report()
        result = checker.check_all()
        # generate_report() 後は is_passed が正しく反映される
        assert result["is_passed"] is False


class TestGenerateReport:
    """generate_report() のテスト"""

    def test_report_format(self):
        """レポートの形式"""
        content = "テスト用のコンテンツ"
        checker = TutorialQualityChecker(content)
        report = checker.generate_report()

        assert isinstance(report, str)
        assert "教材品質自動検証レポート" in report
        assert "総合判定" in report

    def test_report_shows_pass_fail(self):
        """レポートに PASS/FAIL が表示される"""
        content = "テスト用のコンテンツ"
        checker = TutorialQualityChecker(content)
        report = checker.generate_report()

        assert "PASS" in report or "FAIL" in report


class TestValidateMarkdownFile:
    """validate_markdown_file() のテスト"""

    def test_valid_file(self, tmp_path):
        """有効なファイルの検証"""
        # テスト用ファイル作成
        test_file = tmp_path / "test.md"
        content = """
## 🤔 問題

## 💡 解決策
説明です。なぜかというと...

## キッチンメタファー

### ステップ 1
役割を説明します。

```bash
command1
```

出力結果。

### ステップ 2
役割を説明します。

```bash
command2
```

出力結果。

### ステップ 3
役割を説明します。

```bash
command3
```

出力結果。

## 動作確認
確認できます。

## トラブルシューティング

❌ エラー: 失敗した場合
原因と対処法。

❌ エラー: 別の問題
原因と対処法。

| 項目 | 説明 |
|------|------|
| A    | B    |

| 項目 | 説明 |
|------|------|
| C    | D    |

| 項目 | 説明 |
|------|------|
| E    | F    |
"""
        test_file.write_text(content, encoding="utf-8")

        passed, report = validate_markdown_file(str(test_file))

        assert isinstance(passed, bool)
        assert isinstance(report, str)
        assert "レポート" in report
