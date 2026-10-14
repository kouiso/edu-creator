"""
=============================================================================
Golden Dataset (ゴールデンデータセット)
LLM-as-Judge評価のためのテストケース集

柱5: 評価エンジニアリング
- 各AI機能に最低5件のテストケース
- プロンプト変更時の回帰テストが可能
- 「なんとなく良くなった」ではなく数値で判断
=============================================================================
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GoldenTestCase:
    """ゴールデンテストケース"""

    id: str
    description: str

    # 入力（ファイルパスまたは直接コンテンツ）
    content_path: str | None = None
    content: str | None = None

    # 期待されるスコア
    expected_scores: dict[str, int] = field(default_factory=dict)

    # 期待される総合スコア
    expected_overall: float | None = None
    expected_overall_min: float | None = None  # 最低でもこれ以上
    expected_overall_max: float | None = None  # 最高でもこれ以下

    # 必須キーワード
    must_include: list[str] = field(default_factory=list)

    # 禁止キーワード
    must_not_include: list[str] = field(default_factory=list)

    # メタデータ
    category: str = "general"
    difficulty: str = "medium"  # easy, medium, hard
    edge_case: str | None = None


# =====================================
# 良い例（高スコアであるべき）
# =====================================

GOOD_EXAMPLES = [
    GoldenTestCase(
        id="TC001_good_variable_explanation",
        description="良い変数説明のサンプル - メタファーと具体例が豊富",
        content="""
# Day 02: 変数と型の基本

## はじめに

プログラミングを始めると、最初に出会う概念が「変数」です。
変数がわからないと、その先に進むことができません。

今回は、変数の基本を「名前のついたお弁当箱」というメタファーで理解しましょう。

## 変数とは何か

変数（へんすう：データを一時的に保存する場所）は、プログラムの中でデータを一時的に保存しておくための「名前のついたお弁当箱」のようなものです。

| 日常の例 | プログラミング | 説明 |
|---------|--------------|------|
| お弁当箱 | 変数 | データを入れる容器 |
| お弁当箱の名前 | 変数名 | 識別するための名前 |
| お弁当の中身 | 値 | 実際のデータ |
| お弁当箱のサイズ | 型 | 入れられるデータの種類 |

## Step 1: 変数を宣言する（3分）

```typescript
// filepath: src/app/page.tsx
// 名前という変数を宣言し、「田中」という文字列を代入
const name = "田中";
```

確認ポイント:
- ファイルを保存した
- エラーが出ていない

## Step 2: 変数を使う（4分）

```typescript
// filepath: src/app/page.tsx
// 変数nameの値をコンソールに出力
console.log(name);  // "田中" と表示される
```

確認ポイント:
- ブラウザの開発者ツールを開いた
- コンソールに「田中」と表示された

## まとめ

変数は「名前のついたお弁当箱」です。データを入れて、名前で呼び出せます。

```mermaid
graph LR
    A[変数名] --> B[変数]
    B --> C[値]
```
""",
        expected_scores={
            "clarity": 5,
            "accessibility": 5,
            "engagement": 5,
            "actionability": 4,
            "self_containment": 5,
        },
        expected_overall_min=4.0,
        must_include=["メタファー", "表", "確認ポイント", "filepath:"],
        must_not_include=["同様に", "以下略", "簡単です"],
        category="basics",
        difficulty="easy",
    ),
    GoldenTestCase(
        id="TC002_good_docker_setup",
        description="良いDocker説明 - キッチンメタファーが一貫",
        content="""
# Day 01: 環境構築の第一歩

## はじめに

開発環境の構築は、料理を始める前にキッチンを整えるようなものです。
今回は、Taskfileを使って「レシピ通りに」環境を整えましょう。

## キッチンメタファーで理解する

| キッチン | 技術 | 役割 |
|---------|------|------|
| コンロ | Node.js | プログラムを「調理」する |
| キッチン一式 | Docker | 道具を箱に詰めて持ち運ぶ |
| 冷蔵庫 | PostgreSQL | 食材（データ）を保存 |
| レシピカード | Taskfile | 複雑な手順を1ステップに |

## Step 1: Node.jsのバージョン確認（3分）

```bash
$ node -v
v22.11.0
```

確認ポイント:
- v22.x.x が表示された
- もし v20.x.x でも問題ありません

## Step 2: task initを実行（5分）

```bash
$ task init
task: [init] docker compose down --volumes
task: [init] npm ci --legacy-peer-deps
All setup complete!
```

確認ポイント:
- 「All setup complete!」が表示された
- エラーメッセージが出ていない

## アーキテクチャ図

```mermaid
graph LR
    A[User] -->|localhost:3000| B[Next.js]
    B -->|API| C[Backend]
    C -->|Query| D[PostgreSQL]
```

## まとめ

Taskfileを使えば、複雑なセットアップも1コマンドで完了します。
""",
        expected_scores={
            "clarity": 5,
            "accessibility": 5,
            "engagement": 5,
            "actionability": 5,
            "self_containment": 5,
        },
        expected_overall_min=4.5,
        must_include=["キッチン", "表", "mermaid", "確認ポイント"],
        category="setup",
        difficulty="easy",
    ),
]

# =====================================
# 悪い例（低スコアであるべき）
# =====================================

BAD_EXAMPLES = [
    GoldenTestCase(
        id="TC010_bad_skip_words",
        description="悪い例 - 禁止ワードを多用",
        content="""
# Day 03: コンポーネント作成

## はじめに

コンポーネントは簡単です。すぐに理解できます。

## 手順

Step 1と同様に、他のファイルも修正してください。
残りのコンポーネントも同じように作成します。

詳細は公式ドキュメントを参照してください。
以下略。
""",
        expected_scores={
            "clarity": 1,
            "accessibility": 2,
            "engagement": 1,
            "actionability": 1,
            "self_containment": 1,
        },
        expected_overall_max=2.0,
        must_not_include=[],  # これらが含まれているのが問題
        category="negative",
        difficulty="easy",
        edge_case="forbidden_words",
    ),
    GoldenTestCase(
        id="TC011_bad_no_explanation",
        description="悪い例 - 専門用語の説明がない",
        content="""
# Day 05: APIエンドポイント

## 手順

tRPCでCRUDを実装します。
Prismaのスキーマを更新してmigrateを実行。
NextAuthでセッション管理を追加。

```typescript
const router = createTRPCRouter({
  getAll: publicProcedure.query(({ ctx }) => {
    return ctx.db.task.findMany();
  }),
});
```

zodでバリデーションを追加してください。
""",
        expected_scores={
            "clarity": 2,
            "accessibility": 1,
            "engagement": 1,
            "actionability": 2,
            "self_containment": 2,
        },
        expected_overall_max=2.5,
        category="negative",
        difficulty="medium",
        edge_case="missing_explanations",
    ),
    GoldenTestCase(
        id="TC012_bad_no_visuals",
        description="悪い例 - ビジュアル要素がない",
        content="""
# Day 04: データベース設計

## はじめに

データベースはアプリケーションの心臓部です。今回はPrismaを使ってスキーマを定義します。

## スキーマの作成

Prismaスキーマファイルを作成します。Userモデルを定義し、idとemailとnameのフィールドを追加します。次にTaskモデルを作成し、Userとのリレーションを設定します。

## マイグレーション

prisma migrate devコマンドを実行してマイグレーションを適用します。これによりデータベースにテーブルが作成されます。

## シードデータ

prisma/seed.tsファイルを作成してテストデータを投入します。
""",
        expected_scores={
            "clarity": 3,
            "accessibility": 2,
            "engagement": 1,
            "actionability": 2,
            "self_containment": 2,
        },
        expected_overall_max=2.5,
        category="negative",
        difficulty="medium",
        edge_case="missing_visuals",
    ),
]

# =====================================
# 境界値テスト
# =====================================

EDGE_CASES = [
    GoldenTestCase(
        id="TC020_edge_long_code",
        description="境界値 - コードブロックが長い（25行ギリギリ）",
        content="""
# テスト: 長いコードブロック

```typescript
// filepath: src/components/LongComponent.tsx
// 1行目
// 2行目
// 3行目
// 4行目
// 5行目
// 6行目
// 7行目
// 8行目
// 9行目
// 10行目
// 11行目
// 12行目
// 13行目
// 14行目
// 15行目
// 16行目
// 17行目
// 18行目
// 19行目
// 20行目
// 21行目
// 22行目
// 23行目
// 24行目
// 25行目
```

確認ポイント:
- 25行以内に収まっている
""",
        expected_overall_min=3.0,  # ギリギリOK
        category="edge",
        difficulty="medium",
        edge_case="code_length_boundary",
    ),
    GoldenTestCase(
        id="TC021_edge_empty_section",
        description="境界値 - セクションが空",
        content="""
# テスト: 空のセクション

## はじめに

## 本文

## まとめ
""",
        expected_overall_max=1.5,
        category="edge",
        difficulty="hard",
        edge_case="empty_content",
    ),
]

# =====================================
# 全テストケースの取得
# =====================================

ALL_TEST_CASES: list[GoldenTestCase] = GOOD_EXAMPLES + BAD_EXAMPLES + EDGE_CASES


def get_test_cases(
    category: str | None = None,
    difficulty: str | None = None,
) -> list[GoldenTestCase]:
    """テストケースを取得

    Args:
        category: カテゴリでフィルタ（オプション）
        difficulty: 難易度でフィルタ（オプション）

    Returns:
        list[GoldenTestCase]: フィルタされたテストケース
    """
    cases = ALL_TEST_CASES

    if category:
        cases = [c for c in cases if c.category == category]

    if difficulty:
        cases = [c for c in cases if c.difficulty == difficulty]

    return cases


def get_positive_cases() -> list[GoldenTestCase]:
    """良い例のみを取得"""
    return GOOD_EXAMPLES


def get_negative_cases() -> list[GoldenTestCase]:
    """悪い例のみを取得"""
    return BAD_EXAMPLES


def validate_test_case_result(
    test_case: GoldenTestCase,
    actual_score: float,
    actual_scores: dict[str, int] | None = None,
) -> tuple[bool, list[str]]:
    """テストケースの結果を検証

    Args:
        test_case: テストケース
        actual_score: 実際の総合スコア
        actual_scores: 実際の個別スコア（オプション）

    Returns:
        tuple[bool, list[str]]: (合格, 失敗理由のリスト)
    """
    failures = []

    # 期待される総合スコアの検証
    if test_case.expected_overall is not None:
        if abs(actual_score - test_case.expected_overall) > 0.5:
            failures.append(
                f"Overall score mismatch: expected {test_case.expected_overall}, got {actual_score}"
            )

    if test_case.expected_overall_min is not None:
        if actual_score < test_case.expected_overall_min:
            failures.append(
                f"Overall score too low: expected >= {test_case.expected_overall_min}, got {actual_score}"
            )

    if test_case.expected_overall_max is not None:
        if actual_score > test_case.expected_overall_max:
            failures.append(
                f"Overall score too high: expected <= {test_case.expected_overall_max}, got {actual_score}"
            )

    # 個別スコアの検証
    if actual_scores and test_case.expected_scores:
        for key, expected in test_case.expected_scores.items():
            actual = actual_scores.get(key, 0)
            if abs(actual - expected) > 1:  # 1点以上の差を許容しない
                failures.append(
                    f"Score mismatch for {key}: expected {expected}, got {actual}"
                )

    return len(failures) == 0, failures
