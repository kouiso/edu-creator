# 日本語の全角記号（（）、：など）は意図した表記なので、紛らわしい文字の警告は外す
# ruff: noqa: RUF002, RUF003
"""PR の担当者とラベル: ブランチ名と変更したファイルの場所から決める。"""

from __future__ import annotations

import fnmatch

BRANCH_LABELS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("feature/", "feat/"), "feature"),
    (("bugfix/", "fix/"), "bugfix"),
    (("hotfix/",), "hotfix"),
    (("chore/", "refactor/"), "chore"),
    (("docs/",), "documentation"),
    (("release/",), "release"),
)

# このリポの作りに合わせた置き場所（Python のツール・生成スクリプト・テスト・設定）
PATH_LABELS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("*.md", "docs/*"), "documentation"),
    (("pyproject.toml", "uv.lock", ".mise.toml"), "dependencies"),
    (("config/*", "config_models.py", ".coderabbit.yaml", "Taskfile.yml"), "config"),
    ((".github/*", "scripts/ci.sh", "scripts/hooks/*", "scripts/guard/*"), "ci"),
    (("tests/*", "test_*.py"), "test"),
)


def branch_label(branch: str | None) -> str | None:
    b = (branch or "").lower()
    for prefixes, label in BRANCH_LABELS:
        if b.startswith(prefixes):
            return label
    return None


def path_labels(paths: list[str]) -> list[str]:
    labels: list[str] = []
    for patterns, label in PATH_LABELS:
        if any(fnmatch.fnmatch(p, pat) for p in paths for pat in patterns) and label not in labels:
            labels.append(label)
    return labels


def labels_for(branch: str | None, paths: list[str]) -> list[str]:
    """付けるラベル（重複なし・ブランチ由来が先）。既にあるラベルは消さない前提で足すだけ。"""
    out = [x for x in [branch_label(branch)] if x]
    for label in path_labels(paths):
        if label not in out:
            out.append(label)
    return out
