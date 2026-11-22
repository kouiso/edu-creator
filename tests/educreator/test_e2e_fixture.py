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
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from e2e_task import CASSETTE, FIXTURE, VERIFY, make_request, make_task

from educreator import skill
from educreator.cassette import CassetteMismatch
from educreator.checks import get, qa_config, run_check
from educreator.profiles import load_profile
from educreator.write import _request_key, request_for, write_step

FACTS = "- 教材: 見本（全 2 日。配布: zip。技術: flask）\n- 学習者: プログラミング未経験\n"
CONTEXT_LINE = (
    "- 前の Day までに説明した用語: 関数・リスト・f 文字列・for（Day01 の Step 1 まで）\n"
)
BUDGET = {"copy_lines": 200, "files": 5, "minutes": 120, "new_concepts": 3, "code_block_lines": 25}


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


def _request(tree, task=None, **kw):
    return request_for(
        task or make_task(tree), tree, load_profile("flask"), block_lines=25, max_files=1, **kw
    )


def test_request_for_course_facts(tree):
    req = _request(tree, course_facts=FACTS)
    assert CONTEXT_LINE + FACTS in req.prompt
    # 空なら今の依頼文と同じ（録画の鍵が変わらない）
    assert _request(tree).prompt == make_request(tree).prompt
    assert FACTS not in make_request(tree).prompt


def test_request_for_skills_adds_skill_tool_and_guard(tree):
    req = _request(tree, skills=("material-writing",))
    assert req.skills == ("material-writing",)
    assert "Skill" in req.allowed_tools
    assert req.guarded_dir == make_task(tree).material.parent
    plain = make_request(tree)
    assert plain.skills == () and "Skill" not in plain.allowed_tools


def test_request_for_fix(tree):
    fix = "FAIL step-length\nコードブロックが 30 行ある（上限 25 行）"
    task = replace(make_task(tree), fix=fix)
    req = _request(tree, task, course_facts=FACTS)
    assert "今回は新しい Step を足さず" in req.prompt
    assert fix in req.prompt
    assert FACTS in req.prompt
    # 検査の結果は、用語の行（context）にも新しい Step を書く依頼の文にも入らない
    assert CONTEXT_LINE not in req.prompt
    assert "今から Step を1つだけ書きます" not in req.prompt
    assert "material/day01_todo.md" in req.prompt
    assert "コードブロックは 25 行まで" in req.prompt
    # fix が空なら今まで通りの依頼
    assert _request(tree, replace(make_task(tree), fix="")).prompt == make_request(tree).prompt


def test_step_checks_take_material_dir(tree):
    write_step(make_request(tree), account=None, cassette_path=CASSETTE)
    cfg = qa_config("flask", {}, tree, BUDGET)
    for check_id in (
        "step-length",
        "code-completeness",
        "anchor",
        "setext-heading",
        "forward-refs",
    ):
        r = run_check(get(check_id), tree / "material", cfg)
        assert r.ok, f"{check_id}: {r.output}"
    # Day のファイル 1 つを渡すと forward-refs は日のファイルを探せず 2 で終わる
    one = run_check(get("forward-refs"), tree / "material" / "day01_todo.md", cfg)
    assert one.returncode == 2


def test_request_key_is_unchanged_without_skills_and_grows_with_them(tree, tmp_path, monkeypatch):
    plain = _request_key(make_request(tree))
    assert "skills" not in plain and "skills_digest" not in plain
    req = _request(tree, skills=("material-writing",))
    key = _request_key(req)
    assert key["skills"] == ["material-writing"]
    assert key["skills_digest"] == skill.source_digest(("material-writing",))
    # skill の中身を 1 文字変えると鍵が変わる
    copy = tmp_path / "agent-skill"
    shutil.copytree(skill.SKILL_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
    md = copy / "material-writing" / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8") + "。", encoding="utf-8")
    monkeypatch.setattr(skill, "SKILL_DIR", copy)
    assert _request_key(req)["skills_digest"] != key["skills_digest"]
    assert _request_key(req) != key


def test_existing_cassette_still_replays_without_skills(tree):
    res = write_step(make_request(tree), account=None, cassette_path=CASSETTE)
    assert res.ok


def test_course_facts_builds_the_two_lines_from_a_spec():
    from educreator.spec import CourseSpec

    spec = CourseSpec.model_validate(
        {
            "name": "sample",
            "days": 2,
            "learner": {"description": "未経験", "prior_code_lines_max": 0, "os": ["macos"]},
            "budget": {**BUDGET},
            "stack_profile": "flask",
            "app_repo": ".",
            "material_dir": "material",
            "distribution": {"formats": ["pdf", "zip"]},
        }
    )
    assert skill.course_facts(spec) == (
        "- 教材: sample（全 2 日。配布: pdf、zip。技術: flask）\n- 学習者: 未経験\n"
    )
