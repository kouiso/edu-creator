# サブスク認証の設計（Claude と Codex の2本立て）

edu-creator は教材の Step を書く・採点する時に、API キーではなく**サブスクのログイン**で `claude` と `codex` の CLI を子プロセスとして呼ぶ。
この文書は、同じ作りを別のツールが写せるように、決めたことと確かめた事実を書く。
下の `<作業用コピー>` は、このブランチを clone したフォルダ（`uv sync --extra dev` 済み）を指す。コマンドは全部そこで動かす。

```bash
git clone <このリポジトリ> <作業用コピー> -b feat/skill-integration
cd <作業用コピー> && uv sync --extra dev
```

## 1. 設計の骨

| 決めたこと | 理由 | 場所 |
|---|---|---|
| ログインは各 CLI に任せる。自前の OAuth を持たない | 資格情報の形と更新は CLI の持ち物。写すと壊れる | `educreator/auth.py` |
| アカウントごとに設定の置き場を分ける（Claude は `CLAUDE_CONFIG_DIR`、Codex は `CODEX_HOME`） | 1つの置き場に2アカウントは入らない（後のログインが上書きする） | `educreator/accounts.py` の `CONFIG_ENV` |
| 資格情報のファイルは読まない・写さない・印字しない | 漏れる経路を作らない | `auth.py` の冒頭 |
| API キーの環境変数は子プロセスに渡さない | 4 の節 | `Account.env()` |
| 1つの Step の途中でアカウントを替えない | 6 の節 | 運用の決まり |

## 2. アカウントの設定（`edu-creator.toml` と `--config`）

設定ファイルが無ければ、既定のアカウントを使う（Claude は `personal-1`〜`personal-3` と `team`、Codex は `personal-1`）。
自分の置き場を使う時は `edu-creator.toml` を書く。書式はこれだけ。

```toml
[state]
dir = "~/.local/state/edu-creator"   # 使用量の窓の記録を置く場所

[accounts.claude.team-a]
config_dir = "~/.claude-team-a"       # CLAUDE_CONFIG_DIR に入る
max_parallel = 1                      # 省略時は Claude が 3、Codex が 1

[accounts.chatgpt.personal-1]
config_dir = "~/.codex"               # CODEX_HOME に入る。Codex の max_parallel は 1 のみ
```

- 探す順: `--config <パス>` があればそれ。無ければカレントから親へ向かって `edu-creator.toml` を探す。それも無ければ既定。
- `accounts` を書いたら既定は丸ごと消える（足し算ではない）。使うアカウントを全部書く。
- 同じ `config_dir` を2つのアカウントに書くとエラー（`..` やシンボリックリンクで同じ場所を指す書き方も同じ物として数える）。
- `--config` が使えるコマンド: `auth login`、`auth status`、`write`、`judge run`。

```bash
uv run edu-creator auth status --config <設定ファイル>
```

## 3. ログインと状態

### `auth login`（人が1回やる。この文書の検証では動かしていない）

```bash
uv run edu-creator auth login --provider claude --account team-a --config <設定ファイル>
uv run edu-creator auth login --provider chatgpt --account personal-1
```

中身は `claude auth login --claudeai` と `codex login` を、そのアカウントの置き場を環境変数に入れて呼ぶだけ。ブラウザで認可する対話の操作なので、AI は代行しない。
`--help` までは確かめてある。ログインの実行は認証を変える操作なので、この文書の検証では動かしていない。

### `auth status`（読むだけ。何回動かしてもよい）

```bash
uv run edu-creator auth status
```

アカウントごとに1行出る。

| 列 | 意味 |
|---|---|
| login | `済`＝ログイン済み、`未`＝未ログイン、`?`＝CLI が30秒以内に応答しなかった等で分からない |
| method | Claude は `authMethod`（サブスクなら `claude.ai`）、Codex はログインできていれば `chatgpt` |
| 置き場 | そのアカウントの `config_dir` |
| 次の行 | 使用量の窓（`5h: 62% 使用（あと1.3時間で戻る）` の形）。記録が無ければ「記録なし」 |

method に API キーと出たら、サブスクではなくキーで動いている印。サブスクでログインし直す。

## 4. API キーを子プロセスに渡さない理由と仕組み

`ANTHROPIC_API_KEY` や `OPENAI_API_KEY` が環境に残っていると、CLI はサブスクではなくキーで課金する。気づかないまま従量課金になる。
だから `Account.env()` が子プロセスの環境から次を外す。

- `ANTHROPIC_API_KEY`、`OPENAI_API_KEY`（全アカウント・全 provider で外す）
- `CLAUDE_CODE_OAUTH_TOKEN`（親に1つあると、全アカウントが同じ人で動いてしまう。外したうえで、そのアカウント専用の変数 `EDU_CREATOR_TOKEN_CLAUDE_<アカウント名の大文字・ハイフンは_>` がある時だけ入れ直す）

そのうえで `CLAUDE_CONFIG_DIR` か `CODEX_HOME` を、そのアカウントの置き場にして渡す。

確かめる試験（キーが入った環境でも、子プロセスの環境に残らないこと）。

```bash
ANTHROPIC_API_KEY=dummy OPENAI_API_KEY=dummy uv run pytest tests/educreator/test_accounts_auth.py -q
```

Claude の実行では、起動時の記録の `apiKeySource` も見る。`none` 以外ならキーで動いている。

## 5. macOS のキーチェーン（この実行で分かった事実）

- macOS の Claude Code は OAuth のトークンをキーチェーンに置く。`CLAUDE_CONFIG_DIR` を付けると別の項目になる（`Claude Code-credentials-<置き場の sha256 の先頭8桁>`。`accounts.py` のコメントに書いた形で、この実行では項目の名前までは確かめていない）。普段の素の `claude` のログインとは別に、`auth login` で入れる必要がある。
- **普通の ssh ではキーチェーンが開かない**。ssh で `claude auth status --json` を動かすと、ログイン済みでも `loggedIn: false` になる。`security show-keychain-info` は「User interaction is not allowed」で終わる。
- したがって、キーチェーンを使うコマンド（Claude の `auth status`、`write` の本番実行、`judge run`）は、**その Mac の画面にログインした側（GUI セッション）から起動済みの tmux サーバ**の中で動かす。
- **ssh から新しく起動した tmux では開かない**。測った結果: 画面側の tmux では personal-1 が `済`・`claude.ai`、ssh から新規に起動した tmux では同じアカウントが `未`・`none`、`security show-keychain-info` は rc 0 と rc 36 で分かれた。tmux であること自体ではなく、サーバがどのセッションで起動したかで決まる。
- 画面側のサーバの探し方: `ps -axo pid,ppid,command | grep tmux` で、親が 1 の古い `tmux -L <名前>` を探す。ソケットは `/private/tmp/tmux-<uid>/<名前>`。見つからない時（画面にログインした人がいない時）は、人に画面で tmux を1つ起動してもらう。

```bash
# ssh から: キーチェーンが開かない事の確認（読むだけ。rc 36 で終わるのが正常）
security show-keychain-info ~/Library/Keychains/login.keychain-db; echo rc=$?

# 画面側のサーバの中で動かす形（出力はファイルに出して、後で読む。終われば自分でセッションが消える）
tmux -L <ソケット名> new-session -d -s auth-check "zsh -lc \"cd <作業用コピー> && uv run edu-creator auth status > <出力ファイル> 2>&1\""
cat <出力ファイル>
```

- WSL や Linux ではキーチェーンが無く、資格情報はファイルに置かれる。ssh でも `loggedIn: true` になる。ここは差が出る所なので、どちらで動かしたかを記録に残す。
- macOS で2つ目以降のアカウントを入れると、置き場を分けても外れる報告がある（二次情報）。入れた後に `auth status` で全員が `済` のままか見る。外れる時は `claude setup-token` のトークンを、そのアカウント専用の変数（4 の節）に入れる。

## 6. 使用量の窓と、アカウントの切り替え

- Claude は5時間の窓と週の上限がある。1アカウントの並列は3までを既定にした（1週目に測って直す前提）。Codex は `auth.json` を並列で共有できないので1。
- 実行のたびに、Claude の `rate_limit_event`（窓ごとの使用率）を `<state.dir>/usage/<provider>-<アカウント名>.jsonl` に追記する。`auth status` が最新の1行を読んで出す。
- 窓が尽きたら、別のアカウント（`--account`）か Codex（`--provider chatgpt`）に替えて、同じ章の続きを書く。切り替えは**人が `--account` を替える**。自動では替えない。
- **1つの Step の途中ではアカウントを替えない**。Step は1回の呼び出しで書き切り、検査（`--verify`）まで通してから次へ進む。途中で替えると、書きかけの内容と使った文脈がアカウントごとにずれる。尽きたら、その Step の呼び出しをやり直す。

## 7. Codex の経路

```bash
uv run edu-creator write --spec <course-spec.yaml> --day 1 --goal "<この Step でやること>" --verify "<動かして確かめる命令>" --provider chatgpt --account personal-1 --config <設定ファイル>
```

中身は `codex exec --json --cd <作業ツリー> --sandbox workspace-write --ignore-user-config <プロンプト>` を呼ぶ形。

- `--ignore-user-config`: 使う人の `config.toml` を読ませない。ログインは `CODEX_HOME` のままなので使える。
- `--sandbox`: 読むだけの依頼は `read-only`、書く依頼は `workspace-write`。
- Codex は Claude Code の plugin を読まない。skill の本文はプロンプトの頭に埋め込む（関門の hook は動かない）。
- `allowed_tools` と `max_turns` に当たる指定が `codex exec` に無く、Codex では効かない。範囲はサンドボックスで縛る。

### いまの状態（2026-11-13 に記録）

- ログイン: 済（`codex login status` が `Logged in using ChatGPT`、`auth status` の行も `済`）。
- 実行: **使用量の上限に当たっていて、Step を書く実行は通らない**（再開は 2026-12-09 と表示された）。成功の流れの録画（カセット）がまだ無く、成功の流れの試験は公開文書の記載に基づく。
- 既知の穴: `runtime/codex.py` は `--skip-git-repo-check` を付けない。**git の作業ツリーでないフォルダを `--cd` に渡すと、Codex が止まる**。実行前に `git init` するか、直す。直しは別の作業にした（この文書では直さない）。

確かめる（`codex exec` が受ける印の確認と、組み立てた命令の試験）。

```bash
codex exec --help | grep -n -e skip-git-repo-check -e ignore-user-config
uv run pytest tests/educreator/test_runtime.py -q
```

## 8. Claude 側の隔離

`claude` は `--setting-sources project,local` で呼ぶ。使う人のファイル（user）の hook と plugin を読ませない。
作業フォルダの `project` と `local` は教材の持ち物なので残す。この指定が `CLAUDE.md` と skill にも効くかは、公式の文書に書かれていない。詳しくは `docs/skill-integration.md` の隔離の節。

```bash
uv run edu-creator write --help
uv run pytest tests/educreator/test_write_cli.py -q
```

## 9. 別のツールが写すもの

1. `accounts.py`: `Account`（provider・名前・置き場・並列数）、`CONFIG_ENV`、`Account.env()`（キーとトークンを外し、置き場を渡す）、`load_accounts()`（toml の読み込みと、同じ置き場の重複の拒否）
2. `auth.py`: `login()`、`status()`、`status_report()`（ログインは CLI に任せる・資格情報は読まない）
3. `usage.py`: 窓の追記と最新の読み出し
4. `runtime/` の命令の組み立て: Claude は `--setting-sources project,local`、Codex は `--ignore-user-config` と `--sandbox`
5. 試験: `tests/educreator/test_accounts_auth.py`（キーが子プロセスに残らない事・同じ置き場の拒否）
6. 運用の決まり: キーチェーンを使う実行は画面側の tmux の中（5）、Step の途中でアカウントを替えない（6）、`auth login` は人がやる（3）
7. 写す時に直す所: 既定のアカウント名（`DEFAULT_ACCOUNTS`）、Codex の `--skip-git-repo-check`（7）

## 10. この文書の検証

新しい clone で、上のコマンドを全部動かして終了コードを記録した。`auth login` は認証を変えるので動かさず、`--help` だけを確かめた。
