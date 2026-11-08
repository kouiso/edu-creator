# 教材の検査の統合（WBS の A3）

両教材（Flask 版と Next.js 版）で育った検査スクリプトを、`educreator/checks/qa/` の1つの版にまとめる。
検査のロジックは1本にし、スタックで変わる値は stack profile の `qa`（`educreator/profiles/*.yaml`）に、
教材で変わる値（公開先のサービス名など）は `course-spec.yaml` の `qa` に置く。

```bash
edu-creator check --list                      # 検査の一覧
edu-creator check --spec course-spec.yaml     # 全部
edu-creator check --spec course-spec.yaml tone no-skip -v
```

検査は環境変数 `EDU_CREATOR_QA_JSON` で値を受け取る。値が無いと動かない（別のスタックの規則で黙って緑にしないため）。

## 取り込みの決まり

1. 取り込み元は、両方にあれば新しく直したほう（今回は Flask 版。Next.js 版から移したときに、値を定数に出す直しが入っていた）
2. スタックの名前・置き場・言語が書かれた定数は `qa` に出す。コメントの中のスタック名も消す（E-4 のテストが `educreator/` 全体を見る）
3. 取り込み元の自己テストは `tests/educreator/qa/selftest_*.py` に名前を変えて持ち、`tests/educreator/test_qa_selftests.py` が1本ずつ動かす
4. 取り込んだら、**両教材の今の本文で、取り込み元と rc と出力が一致する**ことを確かめる（下の表）

## 1バッチ目（2026-11-08）

| 検査の ID | 取り込み元 | 出した値 | 一致（Flask 版 / Next.js 版の本文） |
|---|---|---|---|
| step-length | 両方で同じ | — | rc・出力とも一致 / 一致 |
| step-ref | 両方で同じ | — | 一致 / 一致 |
| tone | 両方で同じ | — | 一致 / 一致 |
| unused-image | 両方で同じ | — | 一致 / 一致 |
| variants | 両方で同じ | — | 一致 / 一致 |
| setext-heading | コメントだけ違う | — | 一致 / 一致 |
| quiz | コメントだけ違う | — | 一致 / 一致 |
| terms | コメントだけ違う | — | 一致 / 一致 |
| fence-roles | Flask 版 | （curriculum_blocks の値を使う） | 一致 / 一致 |
| crossref | Flask 版 | `crossref_ignore` | 一致 / 一致 |
| no-skip | Flask 版 | `gui_services` | 一致 / 一致 |
| code-completeness | Flask 版 | `code_langs` | 一致 / 一致 |

## 2バッチ目（2026-11-08）

| 検査の ID | 取り込み元 | 出した値 | 結果 |
|---|---|---|---|
| ja-latin-space | Next.js 版だけ | — | Next.js 版の本文で取り込み元と一致。Flask 版の本文にも初めて当てて通った |
| ja-line-break | Next.js 版だけ | `jsx_langs`（JSX の無いスタックでは対象外として通す） | Next.js 版の本文で取り込み元と一致 |

取り込まなかったもの: procedure-order（tRPC のルーターの置き場を前提にしている）、false-success・version-split
（JSX のタグ検査と TypeScript のスナップショットに依る。nextjs の profile 専用として次のバッチで扱う）。

## 3バッチ目（2026-11-08）

| 検査の ID | 取り込み元 | 出した値 | 一致（Flask 版 / Next.js 版の本文） |
|---|---|---|---|
| step-time | Flask 版 | `no_table_days`（教材の値） | 一致 / 一致（Next.js 版は `[1, 2, 3, 4]`） |
| why | Next.js 版（「完成コード」の節を除く処理を持つ上位互換） | `code_langs` | 一致 / 一致 |
| visualization | Flask 版 | `screenshot_exempt`・`required_mermaid_days`（教材の値） | 一致 / 一致（Next.js 版は免除4件・mermaid 7日） |

## 4バッチ目（2026-11-08）

| 検査の ID | 取り込み元 | 出した値 | 一致（Flask 版 / Next.js 版の本文） |
|---|---|---|---|
| comprehension | Flask 版 | `tech_terms`（初出で注釈を求める専門用語） | 一致 / 一致 |
| tech-stack | 両方を一般化して書き直した | `tech_stack`（禁止・使用のパターン、大文字小文字の扱い、文面） | 一致 / 一致 |

tech-stack のコードブロックの取り出しは、言語名の後ろに属性が続く開き行（` ```typescript apply path=... `）も拾う
Flask 版の書き方に揃えた。Next.js 版の取り出し方では属性付きのブロックが検査をすり抜けていたが、今の本文では結果は変わらなかった。

## 5バッチ目（2026-11-08）

| 検査の ID | 取り込み元 | 出した値 | 結果 |
|---|---|---|---|
| anchor | Flask 版（置き場を値から作る）に、Next.js 版の「読み比べ用の節の1行目の目印」の検査を足した | `code_langs`、完成版の根は course-spec の `app_repo` | 両方の取り込み元の自己テストを通り、両教材の本文で取り込み元と一致 |

anchor の自己テストは完成版のリポジトリに実在するファイルを見るので、取り込み元を edu-creator の隣に clone してあるときだけ動き、無ければ skip する。

zip-reference と sale-package は、配布 ZIP の中身を各リポジトリのビルドの仕組み（`Makefile`・`build-zip.sh`）から読むので、
梱包を作る A8 と一緒に統合する。

共有の部品: `markdown_scan.py`（両方で同じ）、`fence_roles.py`、`curriculum_blocks.py`（`code_langs`・`real_prefixes`・
`real_root_files`・`real_root_files_manifest` を `qa` から受け取る。書き込み先の目印は両スタックの書き方を全部受ける）。

## 残り（次のバッチ）

| 種類 | 検査 | 統合で要ること |
|---|---|---|
| 両方にあり中身が違う | zip-reference・sale-package（A8 と一緒に） | 差を読み、スタックの語の一覧（comprehension の技術語、tech-stack の禁止ライブラリ）を `qa` に出す |
| Next.js 版だけ | complete-code・complete-section-fences・false-success・procedure-order・tag-balance・unclosed-screen・version-split・scaffold-src-sync・scaffold-curriculum-alignment | JSX 固有のもの（jsx-marker・tag-balance）は nextjs の profile だけで有効にする |
| Flask 版だけ | day-budget（Day 予算の4軸）・day-trees・scaffold-zip-sync | day-budget は `course-spec.yaml` の `budget` を上限に使う |
| まだ無い | 想定エラーの枠（G12）・テンプレートのクラス名の存在（R3a の配布 CSS ができてから） | 新しく書く |
| 文章の検査 | run_writing_lint（両方で同じ。textlint の設定も1つにまとめる） | 辞書の置き場を `qa` に出す |
