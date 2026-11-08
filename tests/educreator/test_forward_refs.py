"""check_forward_refs（R-5）のテスト。"""

from pathlib import Path

from educreator.checks import get, qa_config, run_check


def _day(n: int, body: str) -> str:
    return f"# Day {n:02d}\n\n{body}\n"


def _py(target: str, code: str, info: str = "python") -> str:
    return f"```{info}\n# filepath: {target}\n{code}\n```\n"


def _run(tmp_path: Path, days: dict[int, str], **qa) -> tuple[int, str]:
    mat = tmp_path / "material"
    mat.mkdir(exist_ok=True)
    for n, body in days.items():
        (mat / f"day{n:02d}_x.md").write_text(_day(n, body), encoding="utf-8")
    r = run_check(get("forward-refs"), mat, qa_config("flask", qa, tmp_path))
    return r.returncode, r.output


def test_use_before_definition_in_same_file_is_reported(tmp_path):
    rc, out = _run(
        tmp_path,
        {
            1: _py("app/a.py", "def normalize(url):\n    return _postgres_url(url)"),
            3: _py("app/a.py", "def _postgres_url(url):\n    return url"),
        },
    )
    assert rc == 1
    assert "`app/a.py: _postgres_url`（Day01 で使い、定義は Day03）" in out


def test_same_name_in_another_file_is_not_confused(tmp_path):
    rc, out = _run(
        tmp_path,
        {
            1: _py("app/a.py", "def show():\n    return helper()")
            + _py("app/b.py", "def helper():\n    return 1"),
            3: _py("app/c.py", "def helper():\n    return 2"),
        },
    )
    assert rc == 0, out


def test_imports_count_as_definitions(tmp_path):
    rc, out = _run(
        tmp_path,
        {
            1: _py(
                "app/f.py",
                "from wtforms import ValidationError\n\ndef check():\n    raise ValidationError('x')",
            ),
            5: _py("app/f.py", "class ValidationError(Exception):\n    pass"),
        },
    )
    assert rc == 0, out


def test_local_names_and_keyword_arguments_are_ignored(tmp_path):
    rc, out = _run(
        tmp_path,
        {
            1: _py(
                "app/r.py",
                "def view():\n    label = 'x'\n    return render(can_edit=True, label=label)",
            ),
            4: _py("app/r.py", "def can_edit():\n    return True\n\ndef label():\n    return 1"),
        },
    )
    assert rc == 0, out


def test_expect_blocks_and_sample_code_are_ignored(tmp_path):
    rc, out = _run(
        tmp_path,
        {
            1: _py("app/a.py", "x = later()", "python expect")
            + "```python\n# filepath: 読み比べ用サンプル（実ファイルには対応しません）\nlater()\n```\n",
            2: _py("app/a.py", "def later():\n    return 1"),
        },
    )
    assert rc == 0, out


def test_approved_forward_ref_passes_with_reason(tmp_path):
    days = {
        1: _py("app/a.py", "def normalize(url):\n    return _postgres_url(url)"),
        3: _py("app/a.py", "def _postgres_url(url):\n    return url"),
    }
    rc, out = _run(
        tmp_path,
        days,
        forward_refs_approved={"app/a.py: _postgres_url": "Day03 まで通らない行と本文で説明"},
    )
    assert rc == 0, out
    assert "了承済み" in out and "本文で説明" in out
