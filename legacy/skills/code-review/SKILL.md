---
name: Code Review
description: 生成コードの正確性・安全性チェック
role: PM (Product Manager)
---

# 🔍 Code Review Skill

## 目的

Scribeエージェントが生成したコードが、**正確で安全で、初心者が学習しやすい**ものであることを保証する。

## レビュー観点

### 1. 正確性 (Correctness)

#### チェック項目
- [ ] コードは意図した動作を実現しているか？
- [ ] 構文エラーや型エラーがないか？
- [ ] 最新のAPIやベストプラクティスに準拠しているか？
- [ ] 非推奨（deprecated）なAPIを使用していないか？

#### よくある問題
- **古いAPIの使用**: React 16の書き方を17/18で使用
- **型定義の不一致**: TypeScriptの型が実際の値と合っていない
- **ライブラリバージョン不整合**: package.jsonのバージョンと異なる書き方

### 2. 安全性 (Safety)

#### チェック項目
- [ ] XSS（クロスサイトスクリプティング）対策がされているか？
- [ ] 入力値のバリデーションがあるか？
- [ ] エラーハンドリングが適切か？
- [ ] 機密情報がハードコードされていないか？

#### 必須パターン

**入力値のバリデーション**
```typescript
// ❌ バリデーションなし
function createUser(name: string) {
  // そのまま使う
}

// ✅ バリデーションあり
function createUser(name: string) {
  if (!name || name.trim().length === 0) {
    throw new Error("名前は必須です");
  }
  if (name.length > 50) {
    throw new Error("名前は50文字以内で入力してください");
  }
  // 処理を続ける
}
```

**エラーハンドリング**
```typescript
// ❌ エラーハンドリングなし
const data = await fetch("/api/users");

// ✅ エラーハンドリングあり
try {
  const response = await fetch("/api/users");
  if (!response.ok) {
    throw new Error(`HTTPエラー: ${response.status}`);
  }
  const data = await response.json();
} catch (error) {
  console.error("データ取得に失敗しました:", error);
  // ユーザーにエラーメッセージを表示
}
```

### 3. 初心者学習適性 (Learnability)

#### チェック項目
- [ ] コードが段階的に理解できる構造か？
- [ ] 一度に多くの概念を詰め込んでいないか？
- [ ] コメントで「なぜ」が説明されているか？
- [ ] 実行して結果が確認できるか？

#### NG パターン

**一度に多くの概念を詰め込む**
```typescript
// ❌ useState, useEffect, useCallback, useMemo を一度に使う
const Component = () => {
  const [data, setData] = useState([]);
  const memoizedValue = useMemo(() => data.filter(x => x.active), [data]);
  const handleClick = useCallback(() => setData([]), []);
  useEffect(() => { /* ... */ }, []);
  // ...
};
```

**OK パターン**
```typescript
// ✅ まずuseStateだけ
const Component = () => {
  const [count, setCount] = useState(0);
  
  return (
    <button onClick={() => setCount(count + 1)}>
      クリック数: {count}
    </button>
  );
};
```

### 4. コード品質 (Quality)

#### チェック項目
- [ ] 変数名・関数名が意味を表しているか？
- [ ] マジックナンバー（意味不明な数値）がないか？
- [ ] 重複コードがないか？
- [ ] 関数が適切な大きさか（長すぎないか）？

## 禁止事項

### 絶対禁止

1. **adhocな改修**
   - その場しのぎのコードは書かない
   - 根本的な解決策を提示する

2. **不必要な暗黙のフォールバック**
   - 要件で明記されない限り、安全のためのフォールバックは不要
   - 「万が一」のコードは書かない

3. **合理的な理由のないオプショナル引数・デフォルト値**
   - デフォルト値は「なぜそれがデフォルトなのか」を説明できる場合のみ

4. **将来的な拡張性の過度な考慮**
   - 今必要なものだけを実装
   - 「将来使うかも」は書かない

5. **初心者が理解できない高度なパターン**
   - HOC（Higher-Order Components）
   - 複雑なジェネリクス
   - 抽象化レイヤーの多重化

### 条件付き使用

**使ってもよいが説明が必要**
- `async/await` → Promise の説明が必要
- `map/filter/reduce` → for文との違いを説明
- `useState` → 状態管理の概念を説明

## レビューテンプレート

### 承認する場合

```markdown
## レビュー結果: ✅ 承認

### 良かった点
- [具体的に何が良かったか]
- [学習しやすい工夫]

### 微修正提案（任意）
- [あればより良くなる点]
```

### 修正が必要な場合

```markdown
## レビュー結果: ⚠️ 修正が必要

### Critical（必須修正）
- **問題**: [何が問題か]
- **理由**: [なぜ問題か]
- **修正案**: [具体的にどう修正するか]

### Major（推奨修正）
- **問題**: [何が問題か]
- **修正案**: [具体的にどう修正するか]

### Minor（余裕があれば）
- [より良くなる提案]
```

## 実例

### 問題のあるコード

```typescript
// ❌ 問題が複数ある
function getData() {
  const url = "https://api.example.com/data";
  const res = fetch(url);
  return res.json();
}
```

**問題点**
1. `async`がない → `await`が使えない
2. エラーハンドリングがない
3. 変数名が不明瞭（`res`は何の略？）
4. URLがハードコード

### 修正後のコード

```typescript
// ✅ 修正後
async function getUserData() {
  // API のエンドポイント（データを取得する場所）
  const apiUrl = "https://api.example.com/data";
  
  try {
    // データを取得
    const response = await fetch(apiUrl);
    
    // エラーチェック
    if (!response.ok) {
      throw new Error(`データ取得失敗: ${response.status}`);
    }
    
    // JSON 形式に変換して返す
    return await response.json();
  } catch (error) {
    console.error("エラーが発生しました:", error);
    throw error;  // エラーを呼び出し元に伝える
  }
}
```

## チェックリスト

レビュー時に以下を確認：

- [ ] コードは正確に動作するか？
- [ ] セキュリティ上の問題はないか？
- [ ] エラーハンドリングは適切か？
- [ ] 初心者が理解できる難易度か？
- [ ] コメントで「なぜ」が説明されているか？
- [ ] 変数名・関数名は意味を表しているか？
- [ ] 一度に多くの概念を詰め込んでいないか？
- [ ] 実行して結果が確認できるか？
