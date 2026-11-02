"""issue・PR・コメント向けの共通自動化（標準ライブラリだけで動く）。

各サブコマンドは .github/workflows/ の workflow から `python3 -m repobot <コマンド>` で呼ばれる。
AI や外部の有料サービスは使わず、文字の規則だけで判定する。
"""
