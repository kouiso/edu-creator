# ✨ edu-creator Engineering Improvements

## 概要（Overview）

AIの「手抜き」や「型崩れ」を、**コードで物理的にガードレール化する**改善を実装しました。

Zodのサフ解析 (SafeParser) の Python版として、Pydantic + 自動ツール化を推し進め、**AI任せから「仕組み任せ」に変更**しています。

---

## 🔧 実装された改善

### 1️⃣ Pydantic による Config の型安全化

**ファイル**: `config_models.py` (新規作成)

TypeScriptの `Zod` 相当を Python で実現。YAML から読み込んだ設定を、AIが動く前に検証します。

#### 何が良くなるか？

```python
# Before（型チェックなし）
config = yaml.load(f)
max_iterations = config["safety"]["max_iterations"]  # 文字列かもしれない...

# After（Pydantic検証）
from config_models import validate_config
success, config, error = validate_config(config_dict)
if not success:
    print(error)  # 設定エラーを即座に検出
    sys.exit(1)

# 検証済みなので型安全
max_iterations = config.safety.max_iterations  # int型で確定
```

#### 定義されたモデル

- **EduConfig**: メイン設定（全体構造）
- **SafetyConfig**: 安全設定（max_iterations, timeout等）
- **LLMConfig**: LLM設定（モデル, 温度等）
- **QualityRulesConfig**: 品質ルール
- **ChapterConfig**: 章の定義
- **OutlineOutput**: AIが生成したアウトラインの検証

#### 自動検証の利点

✅ 必須項目の不足を即座に検出  
✅ 値の範囲チェック（max_iterations は 1-10のみ許可等）  
✅ VS Code の補完が効く  
✅ AIが動き出す前に設定ミスをキャッチ

---

### 2️⃣ Quality Checker の Tool 化

**ファイル**: `quality_checker.py` (拡張)

既存の機械的なチェック（コードブロック長、テーブル数、禁止ワード等）を CrewAI の **Tool** として登録し、Validator エージェントが必ず実行するように強制。

#### 何が良くなるか？

```python
# Tool として登録
@tool
def validate_markdown_tool(markdown_file_path: str) -> str:
    """Markdownの品質を自動検査"""
    # 機械的チェック（AIの主観に依存しない）
    - コードブロック数: 3個以上？
    - テーブル数: 4個以上？
    - 禁止ワード: 「同様に」「残りも」は含まれていない？
    - 絵文字: 各セクションに使われている？
    
    # JSON で返す（AIが確実に読める）
    return json.dumps({
        "passed": True/False,
        "issues": [...],
        "report": "..."
    })
```

#### Validator エージェント に統合

```python
# main.py: Validator に自動チェックツール を付与
validator_tools = scribe_tools + [validate_markdown_structure]
validator = Agent(
    role=VALIDATOR_ROLE,
    goal=VALIDATOR_GOAL,
    backstory=validator_backstory,
    tools=validator_tools,  # ← 自動チェックツール
    ...
)
```

#### 利点

✅ AIの「見た目」判定を機械的チェックに置き換え  
✅ 「100%合格！」という虚偽報告を防止  
✅ 構造的な問題（テーブル不足等）はツールが検出  
✅ AI は「わかりやすさ」などの高度な判定に専念

---

### 3️⃣ Main.py の Config 読み込みの改善

**ファイル**: `main.py` (関数修正)

`load_config()` 関数を Pydantic 検証版に置き換え。

#### Before → After

```python
# Before: 検証なし
def load_config(config_path: str) -> dict:
    config = DEFAULT_CONFIG.copy()
    with open(config_path) as f:
        user_config = yaml.load(f)
    config.update(user_config)  # 型チェック なし
    return config

# After: Pydantic検証
def load_config(config_path: str) -> dict:
    config = DEFAULT_CONFIG.copy()
    with open(config_path) as f:
        user_config = yaml.load(f)
    config.update(user_config)
    
    # Pydantic 検証
    success, validated_config, error = validate_config(config)
    if not success:
        print(f"❌ {error}")
        sys.exit(1)
    
    # 検証済みの設定を返す
    return validated_config.model_dump()
```

#### 効果

✅ YAML パース後、**即座に構文チェック**  
✅ エラー時は分かりやすいメッセージ表示  
✅ 型安全な設定オブジェクトを利用可能

---

### 4️⃣ Validator エージェント のプロンプト拡張

**ファイル**: `prompt/agent/validator.py` (拡張)

プロンプトに「validate_markdown_structure ツールを必ず使用しろ」と明記。

```python
【利用可能なツール】
✅ validate_markdown_structure: Markdown構造を自動検査
  - 必須セクション存在確認
  - コードブロック数・長さ検証
  - テーブル数検証
  - 絵文字使用状況確認
  このツールを必ず使用して、手動判定を機械的なチェックで置き換えてください。

【検証順序】
1. FIRST: validate_markdown_structure ツールを実行
2. THEN: 結果に基づいて、AIしかできない「わかりやすさ」を評価
3. FINAL: 両方の結果を統合したレポートを出力

このアプローチにより、構造的な問題はAIの判断に依存しません。
```

---

## 🚀 使用方法

### 1. Config 検証を確認

```bash
cd edu-creator
source .venv/bin/activate

python -c "
from config_models import validate_config
import yaml

with open('../edu-config.yaml') as f:
    config_dict = yaml.safe_load(f)

success, config, error = validate_config(config_dict)
print(f'✅ Config valid!' if success else f'❌ {error}')
"
```

### 2. 品質チェッカーをテスト

```bash
python -c "
from quality_checker import validate_markdown_tool
import json

# result = validate_markdown_tool('path/to/markdown.md')
# data = json.loads(result)
# print(f'Passed: {data[\"passed\"]}')
"
```

### 3. 通常通り main.py を実行

```bash
python main.py --config ../edu-config.yaml --chapters 1
```

→ Pydantic 検証済み設定で動作開始
→ Validator がツールを使って自動チェック

---

## 📊 今後の改善案

### Phase 2（検討中）

1. **AST検証**: コードブロックを実際に `tsc` / `biome check` で検証
2. **ファイルパス検証**: 「`src/lib/prisma.ts`」という記述が、実際に存在するか確認
3. **自動整形スクリプト**: 「各セクションに絵文字を付ける」のような機械的な修正を Python で自動実行

### Phase 3（検討中）

1. **キャッシング強化**: 検証済みファイルはキャッシュ化
2. **並列検証**: 複数チャプターの検証を並列実行
3. **メトリクス記録**: 各チャプターの「品質スコア」を JSON で記録

---

## 🧠 設計思想

### 「AI任せ」から「仕組み任せ」へ

| 項目 | Before | After |
|-----|--------|-------|
| **Config検証** | AIが「合ってそう」と判断 | Pydantic が型チェック |
| **品質判定** | AIが「合格です！」と判定 | ツール が機械的にチェック |
| **エラー隠蔽** | AIが判定をごまかす可能性 | ツール が客観的に検出 |
| **トークン効率** | AIが説明文を読んで判定 | ツール が即座に判定 |

### Zod との類似性

```typescript
// TypeScript (Zod)
const configSchema = z.object({
  safety: z.object({
    max_iterations: z.number().min(1).max(10),
  }),
});
const result = configSchema.safeParse(config);
if (!result.success) {
  console.log(result.error);
}

# Python (Pydantic)
from pydantic import BaseModel, Field

class SafetyConfig(BaseModel):
    max_iterations: int = Field(ge=1, le=10)

success, config, error = validate_config(config_dict)
if not success:
    print(error)
```

---

## ✅ テスト済み

```bash
✅ Pydantic config validation passed
✅ validate_markdown_tool returns JSON
✅ Quality checker works as CrewAI Tool
✅ Validator agent can load validation tools
```

---

## 💡 次のステップ

1. ✅ 基本的な Pydantic / Tool 化が完了
2. 🔄 実際に main.py で複数チャプター生成テスト
3. 🔄 エラーハンドリングの改善（バリデーションエラー時のAIリトライ等）
4. 📋 ドキュメント作成（開発者向けガイド）

---

## 質問・フィードバック

オーナーの意見を待ってます：

- 「この検証をもっと厳しくしたい」
- 「このチェックは不要」
- 「次はこの部分をやってほしい」

などなど、どんどん言ってくださいね！
