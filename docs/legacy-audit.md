# 旧版（CrewAI）の部品の実態（E-10）

2026-02-03 付けの `IMPLEMENTATION_COMPLETE.md` は「14/14 項目完了」と書いていたが、主張と実装を突き合わせると事実と違ったので消した。
ここには、その文書が挙げていた部品ごとの実態を残す（2026-11-08 に確かめた。確かめ方は下）。

## 突き合わせの結果

| 文書の項目 | ファイル | 実在 | 本体（`main.py`・`main_pm.py`・`edu_creator_main.py`）から使われているか | 文書が書いた効果の測定 |
|---|---|---|---|---|
| 環境別設定（dev/prod） | `config/loader.py`・`config/{dev,prod}-config.yaml` | ある | 使われていない（`config/loader.py` をどこも import しない。`EDU_ENV` を読むのは loader だけ） | — |
| 自動リトライ | `utils/retry_strategy.py`・`core/resilient_llm.py` | ある | 使われていない（retry_strategy を使う resilient_llm を、どこも import しない） | 無い |
| コンテキストの最適化 | `utils/relevance_scorer.py` | ある | 使われていない | 「トークンコスト 20-30% 削減」の測定は無い |
| エージェントの並列実行 | `utils/parallel_executor.py` | ある | 使われていない | 「処理速度 30-40% 削減」の測定は無い |
| 複数 Judge | `utils/multi_judge.py` | ある | 使われていない | 無い |
| ゴールデンテストセット | `tests/golden_test_set.py` | ある | 使われていない（ファイル名が `test_` で始まらず、`test_` の関数も無いので pytest も集めない） | 無い |
| プロンプトの版の管理と A/B | `utils/prompt_version_manager.py` | ある | 使われていない | 無い |
| 分散トレーシング | `utils/tracing.py` | ある | 使われていない | — |
| CoT の解析 | `utils/cot_analyzer.py` | ある | 使われていない（`tests/test_cot_parser.py` が使うのは別の `utils/cot_parser.py`） | — |
| ルータエージェント | `agents/router.py` | ある | 使われていない（`prompt/agent/router.py` は別物のプロンプトの文面） | — |
| PDCA の監視 | `utils/pdca_monitor.py` | ある | 使われていない | — |

ほかに、見出しの「14/14 項目」に対して表は11行で、数も合っていなかった。

## 確かめ方

```bash
# 各モジュールを import している .py を探す（自分自身は除く）
for base in loader resilient_llm retry_strategy relevance_scorer parallel_executor multi_judge \
  golden_test_set prompt_version_manager tracing cot_analyzer router pdca_monitor; do
  grep -rlE "^\s*(from|import)\s+[A-Za-z_.]*\b${base}\b" --include=*.py . | grep -v "\.venv\|/${base}\.py$"
done
```

## この先

旧版は edu-creator 3.0（`educreator/`）を横に育てるストラングラー方式で置き換える。旧版の部品は A11 で `legacy/` に移し、
3.0 が同じ章で Judge に勝ってから消す。3.0 では、部品を足したら本体のコマンドから呼ばれることと、効果を測った数字を
同じ PR に入れる（使われない部品と、測っていない効果を「完了」と書かないため）。
