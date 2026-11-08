"""E-8: 録画した実行で、サンプルアプリの Step を1つ最後まで作る E2E。LLM を呼ばずに CI で通る。

録画は本人のサブスクで手元で作る（tests/educreator/e2e_task.py の依頼。録り直しは `write_step(..., record=True)`）。
ここでは再生して、次を確かめる:
- 作業ツリーのコードが本当に動く（確認のコマンドを実際に打ち、録画のときと同じ出力が出る）
- 本文の Step のコードが、作業ツリーの実ファイルと一致する（恒久ルール: コードは実ファイルから写す）
- 統合した検査に通る
- 依頼が変わったら、古い録画で黙って通さない
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from e2e_task import CASSETTE, FIXTURE, VERIFY, make_request

from educreator.cassette import CassetteMismatch
from educreator.checks import get, qa_config, run_check
from educreator.write import write_step


@pytest.fixture
def tree(tmp_path):
    t = tmp_path / "tree"
    shutil.copytree(FIXTURE, t)
    return t


def test_replayed_step_produces_working_code_and_matching_text(tree):
    res = write_step(make_request(tree), account=None, cassette_path=CASSETTE)
    assert res.ok and res.structured["changed_files"] == ["app/todo.py", "material/day01_todo.md"]

    # 1. コードが本当に動く
    out = subprocess.run(
        VERIFY, shell=True, cwd=tree, capture_output=True, text=True, check=True
    ).stdout
    assert out == "1. 買い物\n2. 洗濯\n"

    # 2. 本文の Step 2 のコードが実ファイルと一致する
    md = (tree / "material" / "day01_todo.md").read_text(encoding="utf-8")
    step2 = md.split("### Step 2:", 1)[1]
    block = re.search(r"```python\n# filepath: app/todo.py\n(.*?)```", step2, re.S)
    assert block is not None
    assert block.group(1) == (tree / "app" / "todo.py").read_text(encoding="utf-8")

    # 本文に書いた確認の出力が、実際の出力と同じ
    assert "1. 買い物\n2. 洗濯" in step2

    # 3. 統合した検査に通る
    cfg = qa_config(
        "flask",
        {},
        tree,
        {"copy_lines": 200, "files": 5, "minutes": 120, "new_concepts": 3, "code_block_lines": 25},
    )
    for check_id in (
        "step-length",
        "code-completeness",
        "anchor",
        "setext-heading",
        "forward-refs",
    ):
        r = run_check(get(check_id), tree / "material", cfg)
        assert r.ok, f"{check_id}: {r.output}"


def test_changed_request_does_not_replay_stale_cassette(tree):
    req = make_request(tree)
    stale = req.__class__(**{**req.__dict__, "prompt": req.prompt + "\n（依頼を変えた）"})
    with pytest.raises(CassetteMismatch):
        write_step(stale, account=None, cassette_path=CASSETTE)


def test_cassette_has_no_machine_paths():
    text = CASSETTE.read_text(encoding="utf-8")
    assert "/home/" not in text and "/Users/" not in text and "/tmp/" not in text
