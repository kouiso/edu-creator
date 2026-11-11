"""cli が spec の置き場から作るパス（相対の spec・章IDの命名）の試験。"""

from pathlib import Path

import yaml

from educreator.cli import main

SPEC = {
    "name": "sample",
    "days": 2,
    "learner": {"description": "未経験", "prior_code_lines_max": 100, "os": ["macos"]},
    "budget": {
        "minutes": 120,
        "new_concepts": 3,
        "files": 5,
        "copy_lines": 200,
        "code_block_lines": 25,
    },
    "stack_profile": "flask",
    "app_repo": "app",
    "material_dir": "material",
    "distribution": {"formats": ["pdf"]},
    "chapters": [
        {"day": 1, "title": "はじめ", "file": "day01_intro.md"},
        {"day": 2, "title": "ログイン", "file": "day02_login.md"},
    ],
}


def _course(root: Path, **over) -> Path:
    (root / "app").mkdir()
    (root / "material").mkdir()
    for n, name in ((1, "intro"), (2, "login")):
        (root / "material" / f"day{n:02d}_{name}.md").write_text(
            f"# Day{n:02d} 題\n\n## Step 1: 開く\n\n本文です。\n", encoding="utf-8"
        )
    p = root / "course-spec.yaml"
    p.write_text(yaml.safe_dump({**SPEC, **over}, allow_unicode=True), encoding="utf-8")
    return p


def test_check_with_relative_spec_and_separate_app_repo(tmp_path, monkeypatch, capsys):
    """spec を相対パスで渡し、app_repo が `.` 以外でも、教材のパスが子プロセスの cwd で切れない。"""
    spec = _course(tmp_path)
    assert main(["check", "--spec", str(spec), "setext-heading", "step-ref"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(tmp_path)
    assert main(["check", "--spec", "course-spec.yaml", "setext-heading", "step-ref"]) == 0
    assert "2/2 件通過" in capsys.readouterr().out


def _judge_setup(tmp_path: Path, monkeypatch, **over):
    from educreator import judge as J

    seen: list[Path] = []

    def fake(md, day, account, state_dir=None, timeout=900):
        seen.append(md)
        return J.JudgeResult(day, "A", {k: 4 for k, _ in J.DIMENSIONS}, {}, "", account.name)

    monkeypatch.setattr(J, "judge_day", fake)
    cfg = tmp_path / "edu-creator.toml"
    cfg.write_text("", encoding="utf-8")
    return seen, cfg


def test_judge_run_finds_chapter_id_material(tmp_path, monkeypatch, capsys):
    mat = tmp_path / "curriculum"
    mat.mkdir()
    (tmp_path / "app").mkdir()
    (mat / "intro.md").write_text("# はじめ\n本文\n", encoding="utf-8")
    (mat / "login.md").write_text("# ログイン\n本文\n", encoding="utf-8")
    spec = tmp_path / "course-spec.yaml"
    spec.write_text(
        yaml.safe_dump(
            {
                **SPEC,
                "material_dir": "curriculum",
                "naming": "chapter-id",
                "chapters": [
                    {"day": 1, "id": "intro", "title": "はじめ", "file": "intro.md"},
                    {"day": 2, "id": "login", "title": "ログイン", "file": "login.md"},
                ],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    seen, cfg = _judge_setup(tmp_path, monkeypatch)
    rc = main(["judge", "run", "--spec", str(spec), "--config", str(cfg), "--days", "1-2"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert [p.name for p in seen] == ["intro.md", "login.md"]


def test_judge_run_still_finds_day_prefixed_material(tmp_path, monkeypatch, capsys):
    spec = _course(tmp_path)
    seen, cfg = _judge_setup(tmp_path, monkeypatch)
    rc = main(["judge", "run", "--spec", str(spec), "--config", str(cfg), "--days", "1-2"])
    assert rc == 0, capsys.readouterr().out
    assert [p.name for p in seen] == ["day01_intro.md", "day02_login.md"]


def test_check_fails_when_a_chapter_file_is_missing(tmp_path, capsys):
    """chapter-id の教材で章のファイルが欠けたら、残りだけを検査して成功にしない。"""
    mat = tmp_path / "curriculum"
    mat.mkdir()
    (tmp_path / "app").mkdir()
    (mat / "intro.md").write_text("# はじめ\n本文\n", encoding="utf-8")
    spec = tmp_path / "course-spec.yaml"
    spec.write_text(
        yaml.safe_dump(
            {
                **SPEC,
                "material_dir": "curriculum",
                "naming": "chapter-id",
                "chapters": [
                    {"day": 1, "id": "intro", "title": "はじめ", "file": "intro.md"},
                    {"day": 2, "id": "login", "title": "ログイン", "file": "login.md"},
                ],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    assert main(["check", "--spec", str(spec), "setext-heading"]) == 2
    assert "login.md" in capsys.readouterr().err
