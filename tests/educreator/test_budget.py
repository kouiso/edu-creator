"""check_budget（Day 予算を本文から実測する）のテスト。"""

from pathlib import Path

from educreator.checks import get, qa_config, run_check

BUDGET = {"copy_lines": 10, "files": 2, "minutes": 60, "new_concepts": 3, "code_block_lines": 25}

DAY = """# Day 01 テスト

**合計時間**: 約{minutes}分

```python
# filepath: app/a.py
# ◆ ファイル全体を置き換え
# ...
x = 1

y = 2
```

```python expect
# filepath: app/a.py
x = 1
y = 2
z = 3
```

```bash
# filepath: app/run.sh
echo 1
echo 2
```

```python
# filepath: 読み比べ用サンプル（実ファイルには対応しません）
a = 1
b = 2
```

```html
{{# filepath: app/templates/b.html #}}
{{# ... #}}
<p>1</p>
<p>2</p>
```
"""


def _run(tmp_path: Path, minutes: int = 50, **overrides) -> tuple[int, str]:
    mat = tmp_path / "material"
    mat.mkdir(exist_ok=True)
    (mat / "day01_test.md").write_text(DAY.format(minutes=minutes), encoding="utf-8")
    cfg = qa_config("flask", overrides, tmp_path, BUDGET)
    r = run_check(get("budget"), mat, cfg)
    return r.returncode, r.output


def test_counts_only_lines_the_learner_types(tmp_path):
    rc, out = _run(tmp_path)
    assert rc == 0, out
    # 数えるのは x・y と <p> 2行の4行。目印・省略・空行・expect・bash・読み比べ用は数えない
    assert "| 01 | 4 | 2 | 50 | 未測定 |" in out


def test_minutes_over_limit_fails(tmp_path):
    rc, out = _run(tmp_path, minutes=75)
    assert rc == 1
    assert "Day01 の分 75 > 60" in out


def test_approved_overrun_passes_with_reason(tmp_path):
    rc, out = _run(tmp_path, minutes=75, budget_approved={1: {"minutes": "ユーザーが了承"}})
    assert rc == 0, out
    assert "了承済み: Day01 の分 75（ユーザーが了承）" in out


def test_report_only_never_fails(tmp_path):
    rc, out = _run(tmp_path, minutes=500, budget_report_only=True)
    assert rc == 0
    assert "超過（報告だけ）: 1 件" in out


def test_copy_lines_are_a_warning_not_a_gate(tmp_path):
    _run(tmp_path)
    cfg_small = {**BUDGET, "copy_lines": 3}
    mat = tmp_path / "material"
    r = run_check(get("budget"), mat, qa_config("flask", {}, tmp_path, cfg_small))
    # 写経の行は周りの行を含む上限値なので、超えても警告だけ（打つ行はリプレイの差分で確かめる）
    assert r.returncode == 0, r.output
    assert "⚠ Day01 の写経の行（上限値）4 > 3" in r.output


def test_missing_budget_is_an_error(tmp_path):
    mat = tmp_path / "material"
    mat.mkdir()
    (mat / "day01_test.md").write_text("# Day 01\n", encoding="utf-8")
    r = run_check(get("budget"), mat, qa_config("flask", {}, tmp_path))
    assert r.returncode == 2
    assert "budget が渡されていない" in r.output
