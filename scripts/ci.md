# ローカルCI

`task ci:fast` は準備済みの依存で重大なRuff違反を検査する。
`task ci` は禁止語検査、gitleaks、依存同期、Ruff、pytestを順に実行する。
既存CIと同じ検査範囲を使う。既存のpytest除外は変更しない。

Python 3.11、uv、gitleaks 8.21.2を用意する。
非公開の禁止語リストは既存のフック設定を使う。
リストやgitleaksがない場合も全検査の成功にはしない。
CIでの秘密の設定とgitleaksの導入は従来の手順を保持する。

`task ci:contract` で実際の共通入口を隔離環境で呼び出す。
検査順序と各処理の失敗伝播を確認できる。
