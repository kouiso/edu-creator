# 書き方の決まり（skill）とプロンプトの組み込み

ほかの教材づくりの場（Flask 版と Next.js 版の 2 つの教材リポジトリ。`docs/checks.md` と同じ呼び方）で育った書き方の決まりを、
edu-creator 3.0（`educreator/`）が Step を書く実行に渡す仕組みの設計。この文書は、skill と hook を Step を書く命令（`edu-creator write`）へ組み込む変更を書く。
skill を読む処理は `educreator/skill.py`、skill の本文と hook は `educreator/agent-skill/`、試験は `tests/educreator/` にある。
この文書は作ってある物の記録で、まだ作っていない物は 2 の「まだ作っていない（後で作る）」だけ（それ以外は、書いた時点で入っている）。
行番号を書いた箇所は、この設計を入れたコミットの時点のファイルの行（関数の名前も併記する）。

何を移すかの決定は、決定表（385 行。列は `repo`・`path`・`blob_sha`・`verdict`・`reason`・`scan`）で行った。
行番号はファイルの行番号（見出しの行が 1 行目）で書く。

| verdict | 行数 | この文書での扱い |
|---|---|---|
| `move-generalized` | 8 | 一般化して下の 1 の置き場に入れる |
| `move-as-is` | 0 | 無い |
| `already-in-edu-creator` | 84 | 取り込み済み（教材の検査 22 本ほか）。置き場を変えない |
| `stay-in-source` | 194 | 元に残す。edu-creator には入れない |
| `third-party-reference-only` | 96 | 第三者の文章術の束 2 つ。複製しない。出典は下の `attribution.md` に書く |
| `drop-with-reason` | 3 | 入れない |

## 1. 置き場

移す物は全部、新しいフォルダ `educreator/agent-skill/` に入れる。skill 1 つにフォルダ 1 つ。
`SKILL.md` の名前だけは大文字で、これは Claude Code が skill の本文を `SKILL.md` という名前で探すため（道具が決める名前）。

```
educreator/agent-skill/
├── course-mission/
│   └── SKILL.md                         … 行 2
├── material-writing/
│   ├── SKILL.md                         … 行 158
│   ├── reference/
│   │   ├── voice-spec.md                … 行 179
│   │   └── attribution.md               … 行 178（元の名前は ATTRIBUTION.md。小文字に直す）
│   └── hook/
│       ├── material_writing_gate.py     … 行 154（元は bash。下の「hook を Python に書き直す理由」）
│       ├── material_writing_reminder.py … 行 155
│       └── material_writing_marker.py   … 行 156
└── curriculum-quality-gate/
    └── SKILL.md                         … 行 210
```

hook のファイル名だけ下線でつなぐのは、試験から `import` して関数を直接呼ぶため（Python のモジュール名に `-` が使えない）。

### 行ごとの置き場と、消す物・一般化する物

元の欄は、取り込み元の文書の種類（skill／hook／プロンプト）と、決定表の行番号だけを書く。元のファイルのパスは書かない。
元の文は、持ち主の手元にある 2 つの取り込み元の教材リポジトリの写し（公開していない）から取った。この文書では 6 の `<取り込み元の clone>` と同じ呼び方をする。
`educreator/agent-skill/` に移した物は一般化した後の結果なので、使う時にも直す時にも取り込みをやり直す必要は無い。
消す物は種類だけを書く（消す文字そのものはこの文書にも写さない）。

| 行 | 元 | 置き場 | 消す物・一般化する物 |
|---|---|---|---|
| 2 | 元の skill／hook／プロンプトの文書（決定表の 2 行） | `educreator/agent-skill/course-mission/SKILL.md` | 元の 6 つの見出し（目的／完了の定義／持ち主の決定／制約／次の一手の選び方／止まって聞くとき）だけを空の型として残す。本文は全部消す: アプリの名前、技術の組み合わせ、売り方の決定、ロードマップの置き場、Day ごとの予定、持ち主の発言の引用、PR の番号、手元の絶対パス。各見出しの下には、値を依頼文のどの行から読むか（下の 4）だけを書く |
| 154 | 元の skill／hook／プロンプトの文書（決定表の 154 行） | `educreator/agent-skill/material-writing/hook/material_writing_gate.py` | Python に書き直す（判定の規則は下の 2 の「関門の hook の判定」）。教材のフォルダを決め打ちで調べる行を消し、守るフォルダは `target.json` から読む。印の置き場は `target.json` の `marker_dir`。拒否の文から、元の教材の外部レビューの経緯とリポジトリの名前を消す。緊急停止のファイル（`.claude/disable-material-writing-gate`）は移さない（下の 2）。Flask 版の変種（行 3。検査を呼ぶように足した物）は使わない |
| 155 | 元の skill／hook／プロンプトの文書（決定表の 155 行） | `educreator/agent-skill/material-writing/hook/material_writing_reminder.py` | Python に書き直す。「作業フォルダの名前に元のリポジトリの名前を含むか」で動く守りを消し、`target.json` の守るフォルダの下かどうかで動かす。目印の文字列（canary）を消す。6 つの手順の文は残す。「`.claude/skills/material-writing/SKILL.md` を読む」という案内は、plugin の中にその置き場が無いので「Skill ツールで `edu-creator:material-writing` を読む」に直す |
| 156 | 元の skill／hook／プロンプトの文書（決定表の 156 行） | `educreator/agent-skill/material-writing/hook/material_writing_marker.py` | Python に書き直す。印の置き場は `target.json` の `marker_dir`（元のリポジトリの名前が入った一時フォルダは使わない）。skill の名前に `material-writing` を含むかの照合は残す（下の 2 の名前 `edu-creator:material-writing` も含むため） |
| 158 | 元の skill／hook／プロンプトの文書（決定表の 158 行） | `educreator/agent-skill/material-writing/SKILL.md` | 節ごとの扱いは下の表。全体から消す物: 元の文書にあった人物設定に固有の言い回しと方言の例、目印の文字列、姉妹のリポジトリの名前、写しを同期する道具の説明、元に残る道具（文章の lint とその包み）への参照 |
| 178 | 元の skill／hook／プロンプトの文書（決定表の 178 行） | `educreator/agent-skill/material-writing/reference/attribution.md` | 「同梱」から「参照」に書き直す。中身は下の「出典の書き方」。同梱した置き場、sha256 の一覧、元のリポジトリの出来事の記録、元に残る道具の呼び方を消す |
| 179 | 元の skill／hook／プロンプトの文書（決定表の 179 行） | `educreator/agent-skill/material-writing/reference/voice-spec.md` | 床・天井・客観ルーブリックを残す。消す物: 名前の出る外部の読み手、比べた他の教材の名前、購入の逸話、元の検査の名前、教材の置き場 |
| 210 | 元の skill／hook／プロンプトの文書（決定表の 210 行） | `educreator/agent-skill/curriculum-quality-gate/SKILL.md` | 元のスクリプトと textlint の命令の一覧を消す。代わりに「検査は edu-creator が Step の後に回す。この実行の中では検査の命令を打たない」と書き、どの検査がいつ回るか（下の 2 の「Step の実行と関門」）を写す。教材の置き場と、技術の組み合わせの例を消す。先頭の `applyTo` を消し、`name: curriculum-quality-gate` と `description` の frontmatter に直す（skill として選べるようにするため） |

### 行 158（`material-writing` の SKILL.md）の節ごとの扱い

節は、元のファイル（決定表の行 158）の見出し。

| 元の節 | 扱い |
|---|---|
| frontmatter | 書き直す。下の「移した skill の frontmatter」 |
| 冒頭の説明と 2 層の説明 | 移さない。共通節と「このリポジトリの値」の 2 層の作りと同期の説明は、写しを 1 つしか持たない edu-creator には要らない |
| 恒久ルール | 移す |
| 優先関係 | 表は移す。表の後の段落から、ほかの skill の名前を消し、「外部の文章術の原則は一致点だけを借り、ぶつかったらこの skill を採る」にする |
| 書く前の 6 つの手順 | 移す |
| レジスタ注意 | 1 つ目の箇条（教材の地の文は敬体）は移す。2 つ目（使う人の手元にある別の skill の扱い）は消す |
| 文体の仕様 | 移す。基調の節の、元の文書にあった人物設定に固有の言い回しと方言の例は消す |
| 密度の考え方 | 移す（CC BY 4.0 の束の文を元にしている。出典の注を残す） |
| guide 08 から採った項目 | 採否の表は移す。元の教材で測った件数と、それを根拠にした文は消し、採否の理由は束のガイドの記述だけにする。B-10 の行の参照先は `edu-creator check` の `tone` にする |
| 採らなかったガイド | 移す（束のガイドの番号と理由だけで、教材に固有の物が無い） |
| writing-lint の精度表・判定の包み・ai-smell-lint | 消す（元の教材で測った数と、元に残る道具の説明） |
| 5 つの不在・教材レジスタでの読み替え | 移す |
| なぜを教える | 移す（MIT の束の 3 原則を元にしている。出典の注を残す） |
| 執筆前チェックリスト | 移す |
| 執筆後のゲート | Gate 1（textlint）は消す（文章の lint は取り込んでいない。`docs/checks.md` の 128 行）。Gate 2 は「edu-creator が回す検査」に置き換え、Gate 2 のコードブロック例外の印の書き方は残す。Gate 3（別のエージェントの冷えた読み手）は、この実行では回さない（下の 2 の「Step の実行と関門」） |
| References | 同梱した束のファイルへの参照と、束の更新の手順・CI の照合の説明を消し、`reference/attribution.md` と `reference/voice-spec.md` への参照だけにする |
| このリポジトリの値・合否の物差し | 消す。Day の数・書き先・コードブロックの上限は依頼文から読み（下の 4）、Gate 3 の読み手像は `learner.description` から読む |

### 移した skill の frontmatter

3 つとも、元の frontmatter（3 つとも先頭の数行）を捨て、次の 2 行に書き直す。
`name` はフォルダの名前と同じにする（plugin の中で `edu-creator:<name>` と呼ぶ名前になるため）。
元の `description` は元の教材の置き場と呼び出し方を書いた文なので移さない。

| skill | `name` | `description` |
|---|---|---|
| course-mission | `course-mission` | `教材づくりの目的・完了の定義・持ち主の決定・制約・次の一手の選び方の型。値は依頼文の「教材」と「学習者」の行から読む。Step を書く前に読む。` |
| material-writing | `material-writing` | `教材の本文（Step）を書く・書き直す前に必ず読む。AI らしい言い回し・翻訳調・手順書化を防ぐ 6 つの手順と文体の仕様、合格の物差し（reference/voice-spec.md）。` |
| curriculum-quality-gate | `curriculum-quality-gate` | `教材の検査は edu-creator が Step の後に回す。この実行の中では検査の命令を打たず、検査の結果が依頼文にあれば、その指摘を直す。` |

### 出典の書き方（`reference/attribution.md`）

第三者の文章術の束 2 つ（CC BY 4.0 の物と MIT の物）は複製しない。ただし行 158 の 6 つの手順・密度の考え方は CC BY 4.0 の束の文を元に書き直した物で、
なぜを教える節は MIT の束の 3 原則を元にしている。だから `attribution.md` に、束ごとに次を書く。

- CC BY 4.0 の束: 作者、題、元の URL、元のコミット、ライセンスの名前と本文の URL（https://creativecommons.org/licenses/by/4.0/ ）、
  「日本語の教材向けに抜き出して書き直した」という変更の注
- MIT の束: 元の URL、元のコミット、ライセンスの名前、元の著作権の行と MIT の許諾の文の全文、使った 3 原則の名前

### 既存の `skills/` と `prompt/` との関係

- `skills/`（`beginner-review` など 5 つ）は旧版（CrewAI）の物。`utils/template_loader.py` の 127 行が `skills/<名前>/SKILL.md` を読み、
  frontmatter の形（`role:`）も違う。3.0 は読まない。旧版を `legacy/` に移す手順は `docs/legacy-audit.md` の「この先」に書いてある。
  新しい skill をここに入れると旧版の読み込みに混ざるので、別のフォルダにした。
- `prompt/`（`agent/`・`task/`・`teaching.py`）は旧版の `core/agent_factory.py` が import するプロンプト。3.0 は読まない。変えない。
- `prompt/instructions/` は、このリポジトリを直す AI への決まり（実行時の教材づくりの決まりではない）。変えない。
- wheel: `pyproject.toml` の `packages` に `educreator` があり、`educreator/profiles/*.yaml` と同じく `.md`・`.py` も入る。
  `tests/educreator/test_wheel.py` に、`educreator/agent-skill/material-writing/SKILL.md` が wheel にある事の確かめがある。

## 2. 実行時にどう読み込まれるか

skill は Step を書く実行（`educreator/write.py`）にだけ渡す。`check`・`replay`・`design`・`judge` は skill を使わない
（Judge には書き方の決まりを渡さない。採点と書き方の物差しを分けておくため）。

### 共通

- `educreator/runtime/base.py` の `AgentRequest` に 2 つの欄を足した。
  - `skills: tuple[str, ...] = ()` … 渡す skill の名前（`educreator/agent-skill/` の下のフォルダ名）。並びは course-spec に書いた順
  - `guarded_dir: Path | None = None` … hook が守る教材のフォルダ
- `educreator/write.py` の `request_for` に引数を 2 つ足した: `request_for(task, tree, profile, block_lines, max_files, skills=(), course_facts="")`。
  - `skills=skills`・`guarded_dir=task.material.parent` を `AgentRequest` に入れる。`skills` が空でなければ `allowed_tools` に `"Skill"` を足す
  - `course_facts` は `PROMPT` の `{context}` の次の行に入れる（下の 4。依頼文に入るので録画の鍵にも入る）
  - `educreator/cli.py` の `_cmd_write`（108〜165 行）が `write` の段で、`load_spec` で読んだ spec から `skills=tuple(spec.skills)` と
    `course_facts=skill.course_facts(spec) if spec.skills else ""`（153 行）を作って `request_for` に渡す。
    `skills` が空の教材では `course_facts` も空で、依頼文は skill を入れる前と同じになる（録画の鍵が変わらない）。`request_for` はほかに `tests/educreator/e2e_task.py` も呼ぶ
- 新しいモジュール `educreator/skill.py` を足した。中身は次のとおり（版の確かめの `claude_version` は下の Claude の節）。
  - `SKILL_DIR = Path(__file__).parent / "agent-skill"`
  - `available_skills() -> list[str]` … `SKILL_DIR` の下で `SKILL.md` を持つフォルダの名前を並べて返す
  - `SOURCE_GLOBS = ("SKILL.md", "reference/*.md", "hook/*.py")` … skill 1 つのフォルダの中で、数える・写すファイルの全部。これ以外（`__pycache__/`・`*.pyc`・`.DS_Store` など）は無い物として扱う
  - `PLUGIN_GLOBS = (".claude-plugin/plugin.json", "skills/*/SKILL.md", "skills/*/reference/*.md", "hooks/*.py", "hooks/hooks.json", "hooks/target.json")` … stage した plugin のフォルダ（`edu-creator/`）の中で数えるファイルの全部
  - `tree_hash(root, globs) -> str` … `root` の下で `globs` のどれかに当たるファイル（`Path.glob` で、`*` は 1 階層。フォルダと symlink は入れない）を、`root` からの相対パス（`/` 区切り）の昇順に並べ、1 つずつ「相対パスの UTF-8・`\0`・中身の長さ（10 進）・`\0`・中身」を sha256 に入れた値の 16 進 64 桁
  - `source_digest(names) -> str` … 選んだ skill を `course-spec` の順に、`"<名前>\0" + tree_hash(SKILL_DIR / 名前, SOURCE_GLOBS)` をつないだ文字列の sha256。録画の照合だけに使う
  - `course_facts(spec) -> str` … 下の 4 の表の行を作る
  - `stage_plugin(names, guarded_dir) -> Path` と `embed(names) -> str` … 下の Claude と Codex で使う
- 一時の置き場は `educreator/runtime/base.py` の `private_dir()`（61〜69 行。自分だけが入れる `edu-creator-<uid>` のフォルダ。
  ほかのユーザーの物や symlink なら `PermissionError`）。以前は `codex.py` の中にあった物を移し、スキーマ・plugin・印の 3 つで使う。

### Claude（`claude -p`）

Claude Code の plugin として、その実行の間だけ読み込ませる。

1. `ClaudeCodeRuntime.build_command`（`educreator/runtime/claude_code.py`）は、`req.skills` が空でなければ
   `skill.stage_plugin(req.skills, req.guarded_dir or req.cwd)` を呼ぶ。作る物は `private_dir()/plugin-<16 桁>/edu-creator/` の下に次の 4 つ。
   - `.claude-plugin/plugin.json` … `{"name": "edu-creator"}`
   - `skills/<名前>/` … `educreator/agent-skill/<名前>/` の `SKILL.md` と `reference/*.md` だけを写す（`SOURCE_GLOBS` のうち `hook/` 以外）
   - `hooks/` … 選んだ skill の `hook/*.py` だけを写す。`hooks/hooks.json` は `educreator/skill.py` の定数 `HOOKS`（下の表）から作るが、写した hook ファイルに当たる項目だけを残す（`_hooks_json`）。hook を持たない skill だけを選ぶと `hooks.json` の `hooks` は空（`{}`）になる（試験: `test_claude_command_without_hook_skills_writes_no_hook_entries`）
   - `hooks/target.json` … `{"guarded_dir": "<守るフォルダ>", "marker_dir": "<private_dir()/marker>"}`。どちらも `os.path.realpath` を通した絶対パス
     （macOS の `/var` と `/private/var` のように、同じ所が 2 つの名前で見えるのをそろえるため）
2. 名前の 16 桁と `digest.txt` は、作る時も使い回す時も同じ 1 つの値 `H = tree_hash(<plugin の edu-creator/ のフォルダ>, PLUGIN_GLOBS)` で決める
   （`digest.txt` は `edu-creator/` の外の `plugin-…/` 直下に置くので数に入らない。hook が `hooks/__pycache__/` を作っても `PLUGIN_GLOBS` に当たらないので `H` は変わらない）。作り方は `codex.py` の 49〜57 行（スキーマのファイル）と同じ考えにする。
   - 作る時: `private_dir()` の下に `plugin-new.<pid>.<乱数>.tmp/` を作り、`edu-creator/` 以下を全部書く。`H` を計算し、`digest.txt` に `H` を書き、
     `os.rename` で `plugin-<H の頭 16 桁>` にする。同じ名前が先にあれば（別の実行が先に作った）、名前を変えずに、先の物を下の使い回しの手順で確かめて使う。
     自分の一時フォルダは、名前を変えなかった時だけ消す（中身は自分しか使っていない）
   - 使い回す時: `plugin-<16 桁>/edu-creator/` について `tree_hash(…, PLUGIN_GLOBS)` を計算し直し、`digest.txt` の中身と一致し、その頭 16 桁が名前と一致すれば使う
   - 一致しない時（途中で止まった・書き換えられた）: そのフォルダは**消しも名前の変更もしない**（ほかの実行の `claude` が使っている途中かもしれない）。
     代わりに `plugin-<16 桁>.<pid>.<乱数>/` という別の名前で作り直し、その実行ではそれを使う。この名前のフォルダは使い回しの対象にしない。
     `private_dir()` は OS の一時フォルダの下なので、残った物は OS の掃除に任せる
3. 命令に次を足す。
   - `--plugin-dir <上の edu-creator のフォルダ>`
   - `--append-system-prompt "教材のファイルに書く前に、Skill ツールで次の skill を順に読む: edu-creator:<名前>, …"`
4. skill は plugin の名前つきで `edu-creator:<名前>` として見える。`--allowedTools` に `Skill` が入っているので、モデルは許可を待たずに読める。

`HOOKS` の中身。どれも `"type": "command"` で、シェルを通さない形（`command` に実行するファイル、`args` に引数の list）で書く。
`<python>` は stage する時の `sys.executable`、`${CLAUDE_PLUGIN_ROOT}` は Claude Code が plugin の置き場に置き換える。
`args` の 2 つ目は、どれも `${CLAUDE_PLUGIN_ROOT}/hooks/target.json`。

| 時機 | matcher | `command` | `args` の 1 つ目 | `onFailure` |
|---|---|---|---|---|
| `PreToolUse` | `Write\|Edit\|NotebookEdit\|Bash` | `<python>` | `${CLAUDE_PLUGIN_ROOT}/hooks/material_writing_gate.py` | `block` |
| `PreToolUse` | `Write\|Edit` | `<python>` | `${CLAUDE_PLUGIN_ROOT}/hooks/material_writing_reminder.py` | 付けない |
| `PostToolUse` | `Skill` | `<python>` | `${CLAUDE_PLUGIN_ROOT}/hooks/material_writing_marker.py` | 付けない |

`onFailure: "block"` は、hook が失敗した時（終了コードが 0 でも 2 でもない、時間切れ、`<python>` が消えて起動できない）に、
通さずに止める指定（Claude Code 2.1.295 から。https://code.claude.com/docs/en/hooks の「Block the action when a hook fails」、2026-11-14 に読んだ）。
付けないと、PreToolUse の hook の失敗は「止めない誤り」として扱われ、操作はそのまま進む（同じ文書の「Other exit codes」）。
関門だけに付ける。案内（reminder）と印（marker）が落ちても、関門が印の無い書き込みを止めるので、止める側は関門 1 か所で足りる。
`onFailure` を読まない古い Claude Code では関門が失敗した時に通ってしまうので、版を確かめる。確かめるのは `stage_plugin` ではなく
`ClaudeCodeRuntime` で、`run()` が起動するのと同じ `self.executable`（`educreator/runtime/claude_code.py` の 26 行）を見る。手元の PATH に版の違う `claude` が
複数あっても、確かめる物と動かす物がずれない。

- `ClaudeCodeRuntime.__init__(self, executable="claude", version_probe=None)` に引数を 1 つ足した。`version_probe` は「版の文字列を返す関数」で、
  `None` なら `skill.claude_version(self.executable)` を使う
- `skill.claude_version(executable) -> str` は `[executable, "--version"]` を `subprocess.run`（`check=False`・`timeout=30`）で打ち、標準出力の最初の
  `数字.数字.数字` を返す（今の出力は `2.1.322 (Claude Code)`）。起動できない・0 以外で終わる・その形が無い時は `RuntimeError` を出す
- `build_command` は `req.skills` が空でない時だけ、最初の 1 回だけ `version_probe()` を呼んで結果をそのインスタンスに覚える。版を数の組で比べ、2.1.295 より前なら
  `RuntimeError("Claude Code 2.1.295 以降が要る（関門の hook の onFailure）。<executable> は <版>")`。`version_probe` が `RuntimeError` を出した時も、そのまま上へ出す
  （版が分からない時は動かさない）。`req.skills` が空なら呼ばないので、skill を使わない今の実行と今の試験（`tests/educreator/test_runtime.py` の 26 行）は変わらない
- 試験は `ClaudeCodeRuntime(version_probe=lambda: "2.1.323")` のように偽の関数を渡し、本物の `claude` を起動しない（CI の `.github/workflows/ci.yml` は `claude` を入れていない）

#### hook を Python に書き直す理由

元の bash の hook は、`jq` が無い時・入力が壊れている時・セッションの番号が取れない時に、何もせず通す（元の関門の該当する分岐）。
edu-creator の実行は人が見ていないので、黙って通ると「読まずに書く」をそのまま見逃す。Python なら `jq` に頼らず JSON を読め、
試験も `jq` の有無で skip しなくてよい。印の置き場も `private_dir()` の下にでき、共有の `/tmp` で別のユーザーが先に作ったフォルダに
印を書けず全部止まる、という壊れ方が無くなる。

#### 関門の hook の判定（`material_writing_gate.py`）

hook が見るのはファイルのパスの形だけで、文の意味は判定しない。

止め方は 2 通りで、どちらも Claude Code の hooks の文書（https://code.claude.com/docs/en/hooks 、2026-11-14 に読んだ）の形。

- 判定して止める時: 標準出力に `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "<理由>"}}` を 1 つ書き、終了コード 0
  （元の bash の関門の該当する分岐と同じ形）
- 判定の途中で例外が出た時: hook の本体を `main()` にまとめ、`run_safely(fn) -> int` が `try: return fn() except BaseException:` で全部受けて、
  標準エラーに「edu-creator の関門の hook が失敗したので止めた: <例外の型と文>」を書いて終了コード 2（PreToolUse で 2 は止める扱い）。
  この 1 か所を抜けて落ちても、上の `onFailure: "block"` が止める

判定の順:

1. 標準入力の JSON が読めない、`target.json` が読めない、入力に `cwd` が無い → 止める（理由の文に「edu-creator の hook が入力を読めなかった」と書く）
2. 対象かどうか。相対のパスは、どれも入力の `cwd` を起点にする（Bash で `cd` した後の作業フォルダ。`CLAUDE_PROJECT_DIR` は `cd` しても変わらないので使わない）。
   起点と合わせたパスを `os.path.realpath` にかけ、`guarded_dir` そのものかその下なら「守るフォルダを指す」とする
   - `Write`・`Edit`・`NotebookEdit`: `tool_input.file_path` が守るフォルダを指し、末尾が `.md` なら対象
   - `Bash`: `tool_input.command` を `shlex.split(posix=True)` で語に分ける（分けられなければ対象にする）。次の 3 つで語をさらに切ってから、どれか 1 つでも守るフォルダを指せば、教材に触れる命令とする
     - 語の中の `>`・`<`・`=` で切る（`x>>material/day01_todo.md`、`--out=material/…` のように、つながって書かれた書き込み先も拾うため）
     - `cd`・`pushd` の次の語も同じに見る（守るフォルダに `cd` してから相対のパスで書く手を拾うため）
     - 例: `python3 x.py material/day01_todo.md` は、`material/day01_todo.md` が守るフォルダを指せば触れる命令になる
   - 触れる命令でも、次の 2 つを両方満たす時だけ「読むだけ」として対象にしない
     - 命令全体が単純な 1 つの命令（`;`・`&`・`|`・`` ` ``・`$(`・改行・`>`・`<` を 1 つも含まない）
     - 最初の語が `cat`・`head`・`tail`・`wc`・`ls`・`stat`・`diff`・`grep`・`cut`・`nl`・`md5`・`md5sum`・`shasum`・`sha256sum` のどれか
       （元の一覧から、ファイルを書き換える・消す・ほかの命令を動かす手を持つ物を外した物。外した物と理由: `git`（`checkout` で戻す）、
       `find`（`-delete`・`-exec`）、`awk`（中で書き込める）、`sort`（`-o`・`--output` で書く）、`uniq`（2 つ目の引数が書き先）、
       `rg`（`--pre` でほかの命令を動かす）、`less`・`more`（`LESSOPEN` などでほかの命令を動かしうる）、`file`（`-C` で引数の隣に `.mgc` を書く）、`egrep`・`fgrep`・`column`（使い道が無いので減らす））
   - それ以外の道具 → 対象にしない
3. 対象で、`session_id` が無い、または `[A-Za-z0-9_.-]+` に全体が合わない（`material_writing_gate.py` の `SAFE_SESSION`）→ 止める。`marker_dir/<session_id>` をそのままパスに使うので、`/` や `..` を含む値で `marker_dir` の外を見に行かせないため
4. 対象で、`marker_dir/<session_id>` が無い → 止める。理由の文は「Skill ツールで `edu-creator:material-writing` を読んでから、同じ操作をやり直す」
5. ほかは何も出さずに終わる（終了コード 0。通す）

元の緊急停止のファイル（`.claude/disable-material-writing-gate`）は移さない。作業フォルダは `guarded_dir` の外なので、
エージェントが自分でそのファイルを作れば関門を外せてしまう。人が止めたい時は、course-spec の `skills` から `material-writing` を外す。

印の hook（`material_writing_marker.py`）は、`tool_input.skill`（無ければ `tool_input.command`）に `material-writing` を含み、`session_id` があれば
`marker_dir/<session_id>` を作る。作れなければ標準エラーに理由を書いて 0 で終わる（関門が `deny` で止め、理由が見える）。
出力の決まり（`material_writing_marker.py` を読んで確かめた）: 標準出力には何も書かない。終了コードは、入力が読めない・skill が対象でない・
`session_id` が使えない形（`[A-Za-z0-9_.-]+` に合わない）・印を作れない、のどれでも 0（標準エラーに理由は書くが止めない）。印を置いた時も 0 で、2 は返さない。

#### 案内の hook の出力（`material_writing_reminder.py`）

止める hook ではなく、`material_writing_reminder.py` を読んで確かめた出力は次の 1 通りだけ。

- 出す条件: 入力が読め、`tool_input.file_path` の末尾が `.md` で、`os.path.realpath` を通したパスが `target.json` の `guarded_dir` そのものかその下にある時
- 出す物: 標準出力に `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "<6 つの手順の案内文>"}}` を 1 つ（`ensure_ascii=False`）。終了コードは 0
- 出さない物: 上の条件に当たらない時と、入力・`target.json` が読めない時（`KeyError`・`ValueError`・`OSError` など）は、何も出さず終了コード 0。止める（2・`permissionDecision`）事は一切しない
- 案内の文は書き込みの後にツールの結果の隣へ届くので、書く前に効かせるのは関門の hook の役目（案内の文の末尾にもそう書いてある）

作業フォルダの `.claude/skills/` に写す形を取らなかった理由: 作業フォルダは学習者の手元と同じツリーで、
`educreator/cassette.py` の `snapshot`・`changes` が録画の差分として拾ってしまう。対象のリポジトリにある `.claude/` も上書きしうる。
`--add-dir` も取らなかった。足したフォルダには書き込みの許可も付くので、`acceptEdits` の実行が skill の本文を書き換えられる。
`--plugin-dir` はその実行の間だけ効き、ファイルの許可は付かない。

### Codex（`codex exec`）

Codex にも自分の skill の仕組みがある（作業フォルダからリポジトリの根までの各階層の `.agents/skills`、`$HOME/.agents/skills`、
`/etc/codex/skills`、同梱の skill。https://developers.openai.com/codex/skills 、2026-11-14 に読んだ）。ただし Claude Code の plugin は読まない。
edu-creator は Codex の skill の置き場は使わず、skill の本文をプロンプトの頭に埋め込む。作業フォルダ（学習者のツリー）に何も書かずに済むため。

- `CodexRuntime.build_command`（`educreator/runtime/codex.py`）は、`req.skills` が空でなければ、最後の引数を
  `skill.embed(req.skills) + "\n\n" + req.prompt` にする。`embed` の形:

```
以下は、この作業で守る書き方の決まり（skill）。作業の前に全部読む。
===== skill: <名前> =====
<SKILL.md の本文。先頭の --- で囲んだ frontmatter は除く>
----- <名前>/reference/<ファイル名> -----
<そのファイルの本文。reference/ の下を名前順に全部>
===== ここまで =====
```

skill が N 個ある時は、`===== skill: <名前> =====` から reference の終わりまでを `req.skills` の順に N 回並べる（見出しは skill ごとに 1 つ）。
終わりの `===== ここまで =====` は全部の後に 1 回だけ付く（skill ごとには付かない）。

- `hook/` は埋め込まない。Codex の側では hook が動かないが、決まりの本文が最初の道具の呼び出しより前に必ずモデルに届くので、
  関門の hook が守っていた「読まずに書く」は起きない。

### 使う人の手元の設定（どちらの CLI にも届く物）

`educreator/accounts.py` の `Account.env`（50〜65 行）は、子プロセスに `CLAUDE_CONFIG_DIR` か `CODEX_HOME` をアカウントの `config_dir` で渡す。
`edu-creator.toml` が無い時の既定は、Claude の `personal-1` が `~/.claude`（ほかのアカウントも `~/.claude-*`）、Codex の `personal-1` が `~/.codex`（同 23 行の `DEFAULT_ACCOUNTS` と、104〜135 行の `load_accounts`）。だから実行には次も届く。

| CLI | 届く物 |
|---|---|
| Claude | `config_dir` の下の `CLAUDE.md`・`skills/`・設定の hook・入れた plugin。作業フォルダの `CLAUDE.md`・`.claude/` |
| Codex | `config_dir`（`CODEX_HOME`）の下の `AGENTS.md`・`config.toml`。上に書いた Codex の skill の置き場。作業フォルダの `AGENTS.md` |

届く物を 2 つに分けて決める。

**使う人の hook と plugin（Claude）: 切り離す。** 使う人の設定にある hook は、Step を書く実行の道具の呼び出しに割り込む。
たとえばコマンドの出力を短く要約する hook があると、Step に写す「実際に出た出力」（`educreator/write.py` の 47 行）が要約に置き換わり、
書き込みを止める hook があれば Step が書けない。hook と、有効にした plugin の一覧は、どちらも設定のファイルに書かれる。
だから `ClaudeCodeRuntime.build_command` は、skill の有無に依らず毎回 `--setting-sources project,local` を付け、使う人の設定のファイル（user）を読ませない
（`claude --help` 2.1.322 の「Comma-separated list of setting sources to load (user, project, local)」）。
`--plugin-dir` は設定のファイルではなく命令の引数なので、edu-creator の plugin はこれでも読み込まれる（上の本物の `claude` の確かめに入れる）。
project と local は作業フォルダ（学習者のツリー）の `.claude/` で、教材のリポジトリの持ち物なので残す。
`--bare`・`--safe-mode` は使わない。`--bare` はサブスクのログイン（OAuth）を読まず、`--safe-mode` は skill と plugin の読み込みも止める（`claude --help` 2.1.322）。

**使う人の `CLAUDE.md` と skill（Claude）、`AGENTS.md` と skill（Codex）: 切り離さない。** 理由は 2 つ。

1. `--setting-sources` が `CLAUDE.md` と skill にも効くかは、skill の公式文書に書かれていない（2026-11-13 に読んだ）。効くと決めつけて頼らない
2. edu-creator の skill は `edu-creator:<名前>` の名前つきで、Codex には本文をそのまま埋め込むので、手元の同じ名前の skill と取り違えない

これも切り離したい人は、`edu-creator.toml` で edu-creator 専用の `config_dir` をアカウントごとに作ればよい（その置き場で `edu-creator auth login` する）。
README には認証の節が無いので、README は変えない。`config_dir` をアカウントごとに分ける書式は `docs/auth-design.md` の 2（`edu-creator.toml` と `--config`）にあり、その置き場で `edu-creator auth login` する。

**Codex の設定のファイル: 切り離す。** `CodexRuntime.build_command` は毎回 `--ignore-user-config` を付け、`CODEX_HOME` の `config.toml` を読ませない
（`codex exec --help` 0.166.0 の「Do not load `$CODEX_HOME/config.toml`; auth still uses `CODEX_HOME`」。ログインはそのまま使える）。

本物の `claude` を 1 回打つ確かめ（命令の形と成功の見分け方は下の 6 の終わり。取り込みの途中で 1 回打って 5/5 通った）で、次の 3 つを見る: `--setting-sources project,local` でもサブスクのログインで動く
（`system` の `init` の `apiKeySource` が `none`。`educreator/runtime/claude_code.py` の 85〜95 行（`parse`）が拾う）、plugin の関門の hook が書き込みを止める、
使う人の設定が読まれていない（`init` の行の plugin の一覧に、使う人が有効にした plugin が無く edu-creator だけがある。
使う人の設定に要約の hook がある手元なら、Step の確認の出力が要約されていない）。使う人の設定のファイルは書き換えない。
`init` の行に plugin の一覧が出ない版だった時は、そこまでを報告に「確かめられなかった」と書く。
Codex の方は、ログインが切れていて今は打てない（`educreator/runtime/codex.py` の 1〜7 行）。打てるようになった時に、同じ形で `--ignore-user-config` でもログインで動く事を見る。

### 録画（カセット）

`educreator/write.py` の `_request_key` は命令の引数を見ないので、skill の中身を直しても古い録画が再生されてしまう。
`_request_key`（`educreator/write.py` の 119 行〜）は、`req.skills` が空でない時だけ `"skills": list(req.skills)` と `"skills_digest": skill.source_digest(req.skills)` を鍵に足す。
空の時は鍵を変えないので、今ある録画（`tests/educreator/fixtures/`）はそのまま通る。`course_facts` と下の検査の結果の行は依頼文に入るので、今の `"prompt"` の鍵で照合される。
`--setting-sources` と `--ignore-user-config` は命令の引数で、どの依頼でも同じなので鍵に入れない。

### Step の実行と関門

1 回の実行が書くのは Day の中の Step 1 つで、作業フォルダには course-spec も検査の道具も無い。だから skill の中の「関門」は次のように分ける。

| 関門 | どこで回るか |
|---|---|
| 書く前の 6 つの手順・文体の仕様・床と天井 | この実行の中。エージェントが skill を読んで守る（Claude は関門の hook が読んだ事を確かめる） |
| Step ごとの検査 | 今の `write` は検査を回さない（`_cmd_write` は `write_step` を 1 回呼んで終わる）。書いた後に、人が `edu-creator check --spec <course-spec> step-length code-completeness anchor setext-heading forward-refs` の 5 本を別に打つ。`edu-creator check` は教材のフォルダ（naming が chapter-id なら `educreator/cli.py` の 89〜93 行の `checks.day_view` を通した物）に回すので、`forward-refs` が Day のファイルを見つけられる。Day のファイル 1 つだけを渡すと、`forward-refs` はそのパスの下から `day[0-9][0-9]_*.md` を探して見つからず、2 で終わる（`educreator/checks/qa/check_forward_refs.py` の 128〜131 行）。1 Step だけの Day でこの 5 本が通る事は、`tests/educreator/test_e2e_fixture.py` の `test_step_checks_take_material_dir`（133〜147 行）が教材のフォルダ（`tree / "material"`）を渡して確かめている。前の Day も一緒に見るが、前の Day はその Day の終わりに通っているので、落ちたら今の Step が原因 |
| Day の全部の検査 | その Day の最後の Step を書いた後に、人が 22 本全部を打つ（`edu-creator check --spec <course-spec>`）。`budget` は `**合計時間**` が無い Day を落とす（`docs/checks.md` の 88 行）ので、Day の途中では回さない |
| 冷えた読み手（元の Gate 3） | Day を書き終えた後の `edu-creator judge run`。書いた会話と別のエージェントが採点する。読み手像は `learner.description` |

#### 検査に落ちた時の直させ方（依頼文の部品だけ作ってある）

`StepTask.fix` と `FIX_PROMPT` は `educreator/write.py` にある。ただし `_cmd_write` は `fix=` を渡さないので、今の `write` からは使われない。

`context` は使わない。`context` は「前の Day までに説明した用語」の行として描かれ（`educreator/write.py` の 91 行）、
`PROMPT` は新しい Step を末尾に足させる（同 38 行と 44 行）ので、そこに入れると検査の結果が用語として届き、直さずに Step を増やしてしまう。

- `StepTask` に欄 `fix: str = ""`（落ちた検査の ID と出力）を足した
- `request_for` は、`task.fix` が空でなければ `PROMPT` の代わりに新しい定数 `FIX_PROMPT` を使うようにした。中身は次の形で、
  `{material}`・`{day}`・`{verify}`・`{marker}`・`{block_lines}`・`{max_files}`・`{course_facts}` は `PROMPT` と同じ値を入れる

```
あなたはプログラミング未経験の人向けの写経教材を書いています。今回は新しい Step を足さず、書き先の最後の Step を直します。

- 作業ツリー: このフォルダ（学習者の手元と同じ、前の Step までのコード）
- 書き先: {material}（Day {day:02d} の本文。直すのは最後の `### Step N:` の節だけ）
{course_facts}- 検査の結果（直す物）:
{fix}
次の順で進めてください。
1. 検査の結果が指す所を、最後の Step の節の中で直す。別の Step の節と、見出しの Step の番号は変えない
2. コードを直す必要があれば、作業ツリーのコードも直し（ファイルは {max_files} つまで）、動かして確かめ（確かめ方: {verify}）、Step のコードと確認の出力を写し直す
3. コードブロックは {block_lines} 行まで。1 行目の書き込み先は {marker} の形
最後に、変えたファイル・確かめたコマンド・Step の見出しを返してください。
```

- 返す形（`SCHEMA`）は今と同じ
- 録画の鍵: `{fix}` を描いた後の文が `"prompt"` に入るので、検査の結果が変われば別の録画になる。鍵の欄は足さない

#### まだ作っていない（後で作る）

次の 3 つは今のコードに無い。`_cmd_write`（`educreator/cli.py` の 108〜165 行）は `write_step` を 1 回呼び、`run_check` を呼ばず、`StepTask` に `fix=` も渡さない。

- `write` が Step を書いた直後に、Step ごとの 5 本（`step-length`・`code-completeness`・`anchor`・`setext-heading`・`forward-refs`）を自分で回す
- Day の最後の Step の後に、22 本を自分で回す
- 検査に落ちたら `fix=` に落ちた検査の ID と出力を入れて `FIX_PROMPT` で直させる。回数は 1 つの Step につき 2 回まで。2 回直しても同じ検査が落ちたら止め、落ちた検査の出力を出して 1 で終わる

それまでは、検査は上の表のとおり人が `edu-creator check` で別に打つ。

## 3. 教材ごとの選び方（`course-spec.yaml` の `skills`）

`educreator/spec.py` の `CourseSpec`（111〜132 行）に、キー `skills` を 1 つ足した。

| 項目 | 値 |
|---|---|
| キー | `skills` |
| 型 | 文字列の list（`list[str]`） |
| 無い時 | `[]`（skill を渡さない。今と同じ動き） |
| 選べる名前 | `course-mission`・`material-writing`・`curriculum-quality-gate`（`educreator/skill.py` の `available_skills()` が返す物） |

```yaml
skills:
  - material-writing
  - curriculum-quality-gate
```

検める決まりは、今ある `_known_profile`（`educreator/spec.py` の 155〜161 行）と同じ形の `field_validator("skills")`（`_known_skills`、134〜145 行）で書いた。

- 知らない名前: `ValueError(f"skill '{name}' は無い。使えるもの: {', '.join(available_skills())}")`
- 同じ名前が 2 回: `ValueError(f"skills に同じ名前が 2 回ある: {dups}")`

`CourseSpec` は `extra="forbid"` なので、キーの名前を打ち間違えた時（例: `skill:`）は今と同じく pydantic の
`Extra inputs are not permitted` で落ちる。どちらの誤りでも、終了コードは今ある段の作りのままになる。

| 命令 | 出力 | 終了コード |
|---|---|---|
| `edu-creator spec check <spec>` | 標準エラーに `<spec>: スキーマに合わない` と、上の文を含む pydantic の文 | 1 |
| `edu-creator write` | 標準エラーに `エラー: ` と、上の文を含む pydantic の文（`_cmd_write` の 133〜135 行） | 2 |
| `edu-creator check`・`replay`・`judge`・`design` | 標準エラーに `エラー: ` と、上の文を含む pydantic の文 | 2 |

この表は `educreator/cli.py` の `_cmd_spec`（41〜43 行）、`_cmd_check`（79〜81 行）、`_cmd_write`（133〜135 行）の作りから書いた。
`skills` についての動きは `tests/educreator/test_spec_lessons.py` の `test_spec_skills_default_is_empty_and_names_are_kept_in_order`（238 行）・
`test_spec_skills_unknown_name_and_duplicates_are_rejected`（244 行）・`test_spec_skills_cli_exit_codes`（253 行）が確かめる。
実行の結果: @@TESTRESULT@@

## 4. 教材に固有の内容の出どころ

アプリの名前・画面・顧客・Day ごとの予定など、教材に固有の内容は edu-creator に置かない。`educreator/agent-skill/` の文は
どの教材にも同じ文で、固有の値は実行の時に、edu-creator が依頼文へ入れた物と作業フォルダから読む。
エージェントは course-spec を読まない（作業フォルダは学習者のツリーで、course-spec は無い。`educreator/write.py` の 109 行で `cwd=tree`）。

| 内容 | 出どころ | エージェントへの届き方 |
|---|---|---|
| 教材の名前・学習者像・日数・配布の形・stack profile | `course-spec.yaml` の `name`・`learner.description`・`days`・`distribution.formats`・`stack_profile` | `_cmd_write` が、`spec.skills` がある時だけ `skill.course_facts(spec)` で次の形の行にし、`request_for` の `course_facts` で依頼文に入れる（`skills` が無い教材では入れない）: `- 教材: <name>（全 <days> 日。配布: <formats>。技術: <stack_profile>）` と `- 学習者: <learner.description>` |
| 1 つのコードブロックの行数・1 回に変えるファイルの数 | `budget.code_block_lines`・`--max-files`（`write` の引数。既定 1。`budget.files` ではない） | 今の `request_for` の `max_files`（`PROMPT` の 42 行。`educreator/cli.py` の 151 行で `args.max_files` を渡し、344 行で `--max-files` を定義）と `block_lines`（同 49 行。`budget.code_block_lines`） |
| 今回書く Day・書き先・やること・確かめ方・前の Day までの用語 | `StepTask` | 今の `PROMPT`（`educreator/write.py` の 35〜51 行の `PROMPT`） |
| 画面・ルート・実際のコード | 作業フォルダ（前の Step までの学習者のツリー） | エージェントが自分で読む |
| 守る教材のフォルダ | `StepTask.material` の親 | `AgentRequest.guarded_dir`。Claude の hook は `target.json` |
| 持ち主の決定・その教材だけの制約 | 対象の教材のリポジトリに残る（決定表で `stay-in-source` にした物） | 渡さない。edu-creator には写さない |

skill の文がエージェントに打たせる命令は無い（検査は上の 2 の「Step の実行と関門」のとおり edu-creator が回す）。

`course-mission` の型の各見出しには、上の表のどの行から値を読むかだけを書く。
目的は依頼文の「教材」と「学習者」の行、完了の定義は「教材」の行の日数と配布の形、制約は依頼文のコードブロックの行数とファイルの数。
持ち主の決定・次の一手の選び方・止まって聞くときは、教材に依らない決まりだけを書く。
実際の文は `educreator/agent-skill/course-mission/SKILL.md` にあり、6 つの見出しの決まりは次のとおり（そのファイルを読んで写した）。

- 1 目的・2 完了の定義・4 制約: 値は依頼文のどの行から読むかだけ。依頼文に無い値を想像で補わない
- 3 持ち主の決定: 依頼文と作業フォルダの文書に書かれた決定だけを知る物とし、蒸し返さず、決定に無い機能や方針を足さない。決めるべき事が見つかったら自分で決めず、最後の返答に事実と選択肢を書く
- 5 次の一手の選び方: 依頼文の Step を 1 つだけ進める。順は、作業ツリーを読む、実コードを 1 か所変える、動かして確かめる、Step を書く。別の作業が見つかっても今回に要る物だけ直し、残りは最後の返答に 1 行で書く
- 6 止まって聞くとき: 依頼文と学習者像の食い違い、日数・配布の形・前提の変更が要る時、自分が変えていない変更を消さないと進めない時、本番・秘密の値・外部への書き込みが要る時は、書かずに最後の返答に理由を書いて終わる

固有の物が入っていない事は、次の 2 つで確かめる。

- `tests/educreator/test_spec_lessons.py` の `test_no_hardcoded_stack_names_outside_profiles`（129〜137 行）は、`educreator/` の `.py` に加えて
  `educreator/agent-skill/` の下の `.md` も見る（hook の `.py` は `educreator/` の `.py` として見られる）
- コミットの前に、禁止語の守り（`scripts/guard/check-forbidden.sh`。pre-commit で動く）が当たり 0 件

## 5. 理想案と現実案

| | 理想案 | 現実案（今回） |
|---|---|---|
| 形 | edu-creator が書き方の決まりの唯一の置き場になり、取り込み元の 2 つの教材リポジトリは写しを持たずに edu-creator を読む | 一般化した写しを edu-creator に置く。取り込み元の物は、いま作っている教材が終わるまでそのまま |
| 良い所 | 直す所が 1 か所。2 か所で別々に直されてずれる事が無い | 取り込み元に何も書かない。リリース済みで動いている教材を止めない |
| 悪い所 | 取り込み元の hook・skill の読み方を変えるので、動いている教材の作業を止める。取り込み元の持ち主の判断が要る | 写しと元の 2 か所になる。元で直した物は、手で写すまで edu-creator に届かない |

今回は現実案にする。理想案への切り替えは、edu-creator のリポジトリに次の題で課題を起票する（番号は起票した後に決まるので書かない）。

> [PBI] 書き方の決まりの置き場を、この道具の 1 か所にまとめる

## 6. 取り込んだ検査が元と同じ結果になる確かめ方

決定表で移すと決めた 8 行に検査は無い（skill・hook・プロンプトだけ）。だから確かめる検査は、取り込み済みの 22 本
（`educreator/checks/__init__.py` の `CHECKS`）のまま。表の行は「検査の ID × 取り込み元」で 22 × 2 ＝ 44 行。
そのうち 6 行は元のスクリプトが無い（`budget` と `forward-refs` は両方に無い新しい検査。`ja-latin-space` と `ja-line-break` は
Flask 版に無い。`docs/checks.md` の 43〜44 行と 79〜106 行）。この 6 行は `by-design` として数える。

### 用意

取り込み元の手元の作業ツリーはチェックアウトもスクリプトの実行もしない（`__pycache__` が書かれるため）。中身を外へ取り出す。

```bash
df -h /
mkdir -p <取り出し先>
git -C <取り込み元の clone> archive <取り込み元の既定のブランチ> | tar -x -C <取り出し先>
```

`<取り込み元の clone>`・`<取り込み元の既定のブランチ>` は、保守者の手元の非公開の入力で、ここには公開しない。
後の `<取り出した元の検査スクリプト>` は、`educreator/checks/__init__.py` の `CHECKS` が並べる検査（`CheckDef` の 2 番目の値がスクリプトのファイル名）の
元のスクリプトで、`<取り出し先>` の中から同じファイル名で探す。

`<取り出し先>/course-spec.yaml` を書く。`CourseSpec`（`educreator/spec.py` の 111〜132 行）の必須のキーを全部書く。
比べるのに効くのは `stack_profile`・`app_repo`・`material_dir`・`naming`・`qa` だけで、ほかの値は形が通れば何でもよい
（`budget` の値を使う検査は `budget` だけで、これは元が無い行）。

Flask 版:

```yaml
spec_version: 1
name: equivalence-flask
days: <日数>
learner:
  description: プログラミングをしたことがない人
  prior_code_lines_max: 0
  os: [macos]
budget:
  minutes: 120
  new_concepts: 3
  files: 5
  copy_lines: 200
  code_block_lines: 25
stack_profile: flask
app_repo: .
material_dir: <material_dir>
naming: day
distribution:
  formats: [zip]
qa:
  gui_services: <取り出した元のスクリプトの GUI サービスの語の一覧を写す>
  real_root_files_manifest: <取り出した元の教材の目録の JSON の、<material_dir> からの相対パス>
```

Next.js 版も、Flask 版と同じ全部のキーを書く。値は次のとおり。`material_dir` と `naming` は、書かないと既定（`naming` は `day`）で動くので、必ず取り出した元に合わせて書く。

```yaml
spec_version: 1
name: equivalence-nextjs
days: <日数>
learner:
  description: プログラミングをしたことがない人
  prior_code_lines_max: 0
  os: [macos]
budget:
  minutes: 120
  new_concepts: 3
  files: 5
  copy_lines: 200
  code_block_lines: 25
stack_profile: nextjs
app_repo: .
material_dir: <material_dir>
naming: <day か chapter-id。取り出した元の章ファイルの名前に合わせる>
distribution:
  formats: [zip]
qa:
  gui_services: <取り出した元のスクリプトの GUI サービスの語の一覧を写す>
  real_root_files: <取り出した元のスクリプトの、ルート直下の写経のファイルの定数を写す>
  no_table_days: <取り出した元のスクリプトの NO_TABLE_DAYS を写す>
  required_mermaid_days: <取り出した元のスクリプトの REQUIRED_MERMAID_DAYS を写す>
  screenshot_exempt: <取り出した元の可視化の検査スクリプトの SCREENSHOT_EXEMPT の 4 項目を、ファイル名と理由のまま写す>
```

`naming` が `chapter-id` の時は、`chapters` に章（`day` と `file`）の一覧も書く。`_cmd_check`（`educreator/cli.py` の 83〜93 行）が `chapters` から `checks.day_view` を作り、
`chapters` にあるファイルが教材のフォルダに無ければ 2 で終わるため。

`qa` の値の出どころ（どれも取り出した元のスクリプトの定数。stack profile の `educreator/profiles/flask.yaml`・`nextjs.yaml` には無いので、書かないと
edu-creator の既定の空で打つことになり、違いが写しの誤りに見える）:

- `gui_services`: 取り込み元の検査 `check_no_skip` のスクリプトが持つ GUI サービスの語の一覧。取り込んだ側は、共通の語に
  `qa.gui_services` を足して使う（`educreator/checks/qa/_config.py` の `GUI_SERVICES`）
- `real_root_files_manifest`（Flask 版）: 取り込み元のスクリプトの対応する定数が、ルート直下の写経のファイルを教材の目録の JSON から作る。
  取り込んだ側は `qa` のこの値から同じ表を作る（`educreator/checks/qa/_config.py`）
- `real_root_files`（Next.js 版）: 取り込み元のスクリプトの対応する定数
- `no_table_days`・`required_mermaid_days`・`screenshot_exempt`（Next.js 版だけ）: 取り込み元の検査 `check_step_time` と可視化の検査のスクリプトの定数。Flask 版は 3 つとも空なので書かない
`screenshot_exempt` を写す物にしたのは、その項目が元の教材の章の題そのもので、この文書に書かない物（上の 4）だから。
`tests/educreator/test_qa_selftests.py` の `ORIGIN`（20〜29 行）も、取り込み元の自己テストを同じ `gui_services`・`real_root_files`・`real_root_files_manifest` で動かしている。

`chapters` を書かない仕様は、`edu-creator spec check` だと `<ファイル> が chapters に無い` を出して 1 で終わる（`check_chapters` が
章のファイルと突き合わせるため）。`edu-creator check` は章立てを突き合わせないので、比べる用途ではそれで足りる。
仕様が読めるかは、次の打ち方の確かめで `step-ref` が 2 で終わらない事で見る。

### 打ち方

元の側（`<取り出し先>` を作業フォルダにして、`python3`）。取り込み元の品質検査の実行スクリプトと同じ分け方にする。

- ファイルごとの 7 本（`visualization`・`step-length`・`no-skip`・`tech-stack`・`code-completeness`・`tone`・`comprehension`）:
  `<material_dir>/` 直下の `day[0-9][0-9]_*.md` と `appendix_*.md` の 1 つずつに
  `python3 <取り出した元の検査スクリプト> <そのファイル>`
- 残りの 15 本: `python3 <取り出した元の検査スクリプト> <教材のフォルダ>` を 1 回

渡すパスは、どちらも `os.path.realpath` にかけた絶対パスにする。edu-creator の側が `target.resolve()` で同じ形にしている
（`educreator/checks/__init__.py` の 157 行）ので、macOS の `/private/var` のような違いが出力に出ない。

ファイルごとの検査は、edu-creator と同じ順・同じまとめ方にする。

- 順: realpath の絶対パスの文字列の昇順（`material_files` が `sorted` で並べる。同 150 行）。だから `appendix_*.md` が `day*.md` より先に来る
- 終了コード: 最初の 0 以外（全部 0 なら 0）
- 出力: 各回の標準出力と標準エラーをつないで前後の空白を落とし、空でない物を改行でつなぐ（同 153〜178 行の `run_check`）

検査の ID とスクリプトの名前の対応は `educreator/checks/__init__.py` の `CHECKS`（`CheckDef("<ID>", "<スクリプト>", …)`）。

edu-creator の側（作業用コピーで）:

```bash
uv run edu-creator check --spec <取り出し先>/course-spec.yaml <検査の ID> -v
```

### 期待する出力と、比べ方

edu-creator の出力は 1 行目が `OK  <ID>` か `FAIL <ID>`、最後の行が `1/1 件通過` か `0/1 件通過`、終了コードは 0 か 1
（`educreator/cli.py` の 98〜105 行）。比べるのは次の 2 つ。

1. 終了コードが 0 か 0 以外か（元は 1 以外の値で終わる事もあるので、値そのものは比べない）
2. edu-creator の出力から 1 行目と最後の行を外した物が、元の側でまとめた出力と同じ

両方が同じなら `match`。最初の 1 回だけ、`step-ref` を両方の取り出し先で打つ。`docs/checks.md` の 27 行では 2026-11-08 に両方の本文で一致したので、
`match` にならなければ、写しの誤りと決める前に打ち方（引数・作業フォルダ・`qa` の値）を疑う。

違う行は種類を 1 つ付ける。`by-design`（取り込みの時に決めて変えた違い。根拠に `docs/checks.md` の行を書く）、
`port-bug`（写しの誤り。edu-creator の写しだけを直し、試験を先に書いてから打ち直す）、
`source-bug`（元のスクリプトの誤り。元は直さず理由を書く）。`kind` の値は `match`・`by-design`・`source-bug`・`port-bug` の 4 つ。

同値確認は、取り込みの時に 1 回、このリポジトリの外にある公開していない補助のツールで行った。そのツールはここに無いので、このリポジトリだけでは同じ実行を再現できない。
このリポジトリだけで作り直すには、`uv run edu-creator check --list` で検査の ID を出し、各 ID を元の木と edu-creator の木の両方で打って、1 行ごとに終了コードと出力が同じかを記録する。
台帳は、その結果を 1 行ずつ足した TSV ファイル 1 つ（補助のツールが作った形。作り直す時も同じ形で手で書く）。
列は左から `check_id`・`repo`・`src_rc`・`edu_rc`・`same_output`・`kind`・`reason`（タブ区切り、1 行目が見出し）。
`src_rc` は元のスクリプトの終了コードで、元が無い行は `-`。`same_output` は `yes`／`no`。`kind` は、終了コードの 0／0 以外が同じで出力も同じ時だけ
ツールが `match` と書き、それ以外は空で出るので、人が `by-design`・`source-bug`・`port-bug` のどれかに埋めて `reason` を書く。
ツールは実行のたびに、台帳の全行を数えて最後に 1 行を出す。合格はその行がちょうど次の形になる事:

```
ROWS=44 EMPTY_KIND=0 PORT_BUG=0
```

補助のツールが無くても、手で書いた台帳は、このリポジトリで次の 1 行で数えられる（`<台帳の TSV>` は台帳のパス。1 行目の見出しは数えない）。

```bash
python3 -c 'import csv,sys; r=list(csv.DictReader(open(sys.argv[1],encoding="utf-8"),delimiter="\t",quoting=csv.QUOTE_NONE)); print("ROWS=%d EMPTY_KIND=%d PORT_BUG=%d"%(len(r),sum(1 for x in r if not (x["kind"] or "").strip()),sum(1 for x in r if x["kind"]=="port-bug")))' <台帳の TSV>
```

合格は `ROWS` が（検査の数 × 2）に等しく（22 本なら 44）、`EMPTY_KIND=0`、`PORT_BUG=0`。

`match` 以外の行は `reason` が空でない事も、台帳を見て確かめる。

### 組み込みそのものの確かめ

```bash
uv run pytest tests/educreator -q   # 終了コード 0
bash scripts/ci.sh fast             # ruff の全ルール・format・mypy。終了コード 0
```

先に書いた試験（旧実装で落ちる事を確かめてから直した）:

| 試験 | 確かめる事 |
|---|---|
| `test_spec_skills_*`（`tests/educreator/test_spec_lessons.py`） | `skills` が無い時は `[]`。知らない名前と重複は上の文で落ちる。`edu-creator spec check` が 1、`edu-creator check` が 2 |
| `test_claude_command_without_hook_skills_writes_no_hook_entries`（同） | hook を持たない skill（`course-mission`）だけで作ると、`skills/course-mission/SKILL.md` があり、`hooks/hooks.json` の `hooks` が `{}` |
| `test_claude_command_with_skills`（`tests/educreator/test_runtime.py`） | `ClaudeCodeRuntime(version_probe=lambda: "2.1.323")` で作る（本物の `claude` を起動しない）。`--plugin-dir` と `--append-system-prompt` が付き、`--allowedTools` に `Skill` が入る。plugin のフォルダに `skills/<名前>/SKILL.md`・`hooks/hooks.json`・`hooks/target.json`・`digest.txt` がある。`hooks.json` の関門だけに `"onFailure": "block"` があり、3 つとも `command` と `args` の形。`--setting-sources project,local` は `skills` の有無に依らず付く。`skills` が空なら、そのほかは今と同じ |
| `test_stage_plugin_reuse`（同） | 同じ中身なら作り直さず同じフォルダを返す。`digest.txt` の中身は、その `edu-creator/` に `tree_hash(…, PLUGIN_GLOBS)` を当てた値と同じ。`hooks/__pycache__/x.pyc` を足しても使い回される。`digest.txt` が無い・中身が合わないフォルダは、消さず名前も変えずに残り、別の名前のフォルダが返る |
| `test_claude_version_gate`（同） | `version_probe` が `"2.1.284"` を返すと `build_command` が `RuntimeError`（文に版と `executable` がある）、`"2.1.295"` なら通る。`version_probe` が `RuntimeError` を出すとそのまま上へ出る。`skills` が空なら `version_probe` は呼ばれない。`claude_version` は、偽の実行ファイル（`2.1.322 (Claude Code)` を出す小さなスクリプト、何も出さないスクリプト、無いパス）で、版・`RuntimeError`・`RuntimeError` を返す |
| `test_source_digest_ignores_cache`（同） | 一時フォルダに作った skill の `hook/__pycache__/x.cpython-312.pyc` と `.DS_Store` を足しても `source_digest` は変わらず、`SKILL.md` を 1 文字変えると変わる |
| `test_codex_prompt_embeds_skills`（同） | 最後の引数が `embed` の形で始まり、元の依頼文で終わる。frontmatter が入らない。`--ignore-user-config` が付く |
| `test_request_for_course_facts`（`tests/educreator/test_e2e_fixture.py`） | `course_facts` が依頼文の `context` の次の行に入る |
| `test_request_for_fix`（同） | `StepTask.fix` が空でなければ `FIX_PROMPT` になり、検査の結果がその行に入り、「新しい Step を足さず」の文がある。`context` の行には入らない |
| `test_step_checks_take_material_dir`（同） | Step ごとの 5 本を教材のフォルダに回すと通り、Day のファイル 1 つを渡すと `forward-refs` が 2 で終わる（渡し方を取り違えた時に気づくため） |
| `test_request_key_*`（同） | skill の中身を 1 文字変えると鍵が変わる。`skills` が空なら鍵は今と同じで、今ある録画が通る |
| `test_skill_hooks.py`（新しいファイル `tests/educreator/test_skill_hooks.py`） | 関門の hook の判定の 1〜5 を 1 つずつ、hook をファイルとして子プロセスで打って確かめる。印が無い時に止まる物: `guarded_dir` の下の `.md` への `Write`、`python3 x.py <相対の教材のパス>`、`printf x>><相対の教材のパス>`、`cd <守るフォルダ>`、入力の `cwd` を守るフォルダの横にして `../<守るフォルダの名前>/day01_x.md` に書く `Bash`、`git checkout -- <教材のパス>`、`find <守るフォルダ> -delete`、`sort -o <教材のパス> <教材のパス>`、`sort --output=<教材のパス> x`、`uniq x <教材のパス>`、`cat <教材のパス> \| tee x`、閉じていない引用符の `Bash`。通る物: 単独の `cat <教材のパス>`、外のパスへの `Write`、印がある時の書き込み。`guarded_dir` を symlink の先で渡しても同じ判定。入力が壊れている・`cwd` が無い時は止まる。止める時の出力は `permissionDecision: deny` の JSON で終了コード 0。**壊れた時**: hook の `if __name__ == "__main__":` の所は `sys.exit(run_safely(main))` の 1 行にし、試験は `run_safely` に例外を出す関数を渡して、2 が返り標準エラーに理由がある事を見る（`main` の中のどこで例外が出ても同じ道を通る）。印の hook が `marker_dir` に印を作る。どれも skip しない（標準の部品だけで動くため） |
| `test_wheel_*`（`tests/educreator/test_wheel.py`） | wheel に `educreator/agent-skill/material-writing/SKILL.md` がある |

`claude -p` が `--plugin-dir` の skill と hook を実際に読み込む事は、試験の偽物では確かめられない。本物の `claude` を打つ。
命令の形は次のとおり（`_cmd_write` の引数。`--day`・`--goal`・`--verify` は必須、`--provider` の既定は `claude`）:

```bash
uv run edu-creator write --spec <course-spec.yaml> --day <Day の番号> --goal "<この Step でやること>" --verify "<動かして確かめる命令>" --config <edu-creator.toml のパス> --cassette <録画の JSON> --record
```

前提: `--spec` の course-spec の `chapters` に、`--day` で渡す Day が書いてあること。無いと `write` は何も実行せず、標準エラーに `エラー: <spec のパス> の chapters に Day <番号> が無い` を出して終了コード 2 で終わる（`educreator/cli.py` の 125〜127 行）。上の命令の例の `<Day の番号>` は、この `chapters` に書いた `day` の 1 つにする。

成功の見分け方: 終了コードが 0、`--cassette` の録画の JSON が書かれる、続けて `uv run edu-creator check --spec <course-spec.yaml> step-length code-completeness anchor setext-heading forward-refs` の 5 本が全部 `OK` で `5/5 件通過`。
これは取り込みの途中で、実際のサブスクのログインを使って 1 回打ち、5/5 通った。録画の JSON と作業フォルダはこのリポジトリに入れていないので、この文書だけでは同じ出力を再現できない（上の形で打ち直せば確かめられる）。
`edu-creator:material-writing` を読む前の書き込みが止まり、読んだ後に通る事の確かめは、この 1 回では記録していない。
plugin の形（manifest は省略できる、`--plugin-dir` では名前がフォルダ名になる、skill は `<plugin>:<skill>` で呼ぶ）は
Claude Code の公式文書（https://code.claude.com/docs/en/plugins-reference と https://code.claude.com/docs/en/skills 、2026-11-13 に読んだ）と、
Claude Code 2.1.322 の `claude --help` で確かめた。
