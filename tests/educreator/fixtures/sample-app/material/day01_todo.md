# Day01 やることを覚える

今日は、やることを足して一覧で見られるようにします。

### Step 1: やることを足す関数を書く（10分）

やることを1つ覚えておく `add` を書きます。足したものを後で一覧に出すためです。

```python
# filepath: app/todo.py
ITEMS: list[str] = []


def add(item: str) -> None:
    ITEMS.append(item)
```

確認方法: `python3 -c "from app.todo import add, ITEMS; add('買い物'); print(ITEMS)"` を実行し、`['買い物']` と出れば正しいです。

| エラーメッセージ | 原因 | 直し方 |
|---|---|---|
| `ModuleNotFoundError: No module named 'app'` | `app` フォルダの外で実行した | プロジェクトのフォルダに移ってから実行する |
