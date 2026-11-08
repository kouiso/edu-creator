# やることを覚えておく小さなアプリ。Day ごとに1つずつ機能を足す
ITEMS: list[str] = []


def add(item: str) -> None:
    ITEMS.append(item)
