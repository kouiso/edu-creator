"""issue・PR の書き方チェック（scripts/repobot/form.py）と見出し修正（heading.py）のテスト。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from repobot import form, heading  # noqa: E402

GOOD_ISSUE = """## 背景
表示が遅い。

## 今どこまで
なし

## 次にやること
1. 計測する

## 誰の判断待ち
磯貝さん: 入れてよいか

## 完了条件
- [ ] 1秒以内に出る
"""

GOOD_PR = """## 概要
キャッシュを足す。

## 変更内容
- cache.py を追加

## 関連Issue
Closes #12
"""


def test_complete_issue_is_green():
    assert form.check_issue(GOOD_ISSUE) == []


def test_missing_heading_is_reported():
    body = GOOD_ISSUE.replace("## 誰の判断待ち\n磯貝さん: 入れてよいか\n", "")
    assert form.check_issue(body) == ["「誰の判断待ち」の見出しがありません"]


@pytest.mark.parametrize(
    "filler",
    ["", "-", "- ", "<!-- ここに書く -->", "- [ ]", "_No response_", "*", "\n\n"],
)
def test_heading_without_content_is_empty(filler):
    body = GOOD_ISSUE.replace("表示が遅い。", filler)
    assert form.check_issue(body) == ["「背景」の中身が書かれていません"]


def test_form_headings_three_hashes_and_notes_are_accepted():
    body = GOOD_ISSUE.replace("## ", "### ").replace("### 背景", "### 背景（必須）")
    assert form.check_issue(body) == []


def test_subheading_content_counts_for_parent():
    body = GOOD_ISSUE.replace("## 次にやること\n1. 計測する", "## 次にやること\n### 手順\n1. 計測する")
    assert form.check_issue(body) == []


def test_headings_inside_code_blocks_are_ignored():
    body = "```\n## 背景\n## 今どこまで\n## 次にやること\n## 誰の判断待ち\n## 完了条件\n```\n"
    assert len(form.check_issue(body)) == 5


def test_empty_or_none_issue_reports_all_five():
    assert len(form.check_issue(None)) == 5
    assert len(form.check_issue("")) == 5


def test_complete_pr_is_green():
    assert form.check_pr(GOOD_PR) == []


def test_org_template_headings_are_accepted_for_pr():
    body = "## 関連 Issue\n\n- Refs #6\n\n## 概要・背景・妥協点\n変える。\n\n## やったこと\n- 足した\n"
    assert form.check_pr(body) == []


@pytest.mark.parametrize(
    "relation, ok",
    [
        ("Closes #3", True),
        ("Refs #3", True),
        ("Refs: #3", True),
        ("fixes kouiso/other#3", True),
        ("No-Close: 理由。 Refs #6", True),
        ("- Closes #", False),
        ("#3", False),
        ("関連なし", False),
    ],
)
def test_pr_relation_needs_closes_or_refs(relation, ok):
    body = GOOD_PR.replace("Closes #12", relation)
    missing = form.check_pr(body)
    assert (missing == []) is ok
    if not ok:
        assert missing == ["「関連Issue」に `Closes #番号` か `Refs #番号` がありません"]


def test_pr_missing_and_empty_sections():
    body = "## 概要\n-\n\n## 関連Issue\nRefs #1\n"
    assert form.check_pr(body) == ["「概要」の中身が書かれていません", "「変更内容」の見出しがありません"]


def test_red_to_green_by_fixing_body():
    broken = GOOD_ISSUE.replace("1秒以内に出る", "")
    assert form.check_issue(broken) == ["「完了条件」の中身が書かれていません"]
    assert form.check_issue(GOOD_ISSUE) == []


def user(login="alice", kind="User"):
    return {"login": login, "type": kind}


@pytest.mark.parametrize(
    "issue, reason",
    [
        ({"user": user(), "title": "普通"}, None),
        ({"user": user("dependabot[bot]", "Bot"), "title": "x"}, "ボットが作った issue"),
        ({"user": user(), "title": "x", "labels": [{"name": "security-alert"}]}, "アラート系のラベル付き"),
        ({"user": user(), "title": "x", "labels": [{"name": "アラート"}]}, "アラート系のラベル付き"),
        ({"user": user(), "title": "[SBI] 分解", "labels": []}, "作業分解（SBI）の issue は本文が空でよい運用"),
        ({"user": user(), "title": "x", "pull_request": {"url": "u"}}, "PR は PR 側で検査する"),
    ],
)
def test_skip_issue(issue, reason):
    assert form.skip_issue(issue) == reason


@pytest.mark.parametrize(
    "pr, reason",
    [
        ({"user": user(), "draft": False}, None),
        ({"user": user("renovate[bot]", "Bot"), "draft": False}, "ボットが作った PR"),
        ({"user": user(), "draft": True}, "下書きの PR"),
    ],
)
def test_skip_pr(pr, reason):
    assert form.skip_pr(pr) == reason


def test_report_lists_missing_and_ok():
    red = form.report("issue", ["「背景」の見出しがありません"])
    assert "足りない所があります" in red and "- 「背景」の見出しがありません" in red
    assert "書き方チェック: OK" in form.report("PR", [])


@pytest.mark.parametrize(
    "before, after",
    [
        ("### 背景\n本文", "## 背景\n本文"),
        ("#### 小見出し", "### 小見出し"),
        ("## そのまま\n# 一番上\n##### 深い", "## そのまま\n# 一番上\n##### 深い"),
        ("###見出しではない", "###見出しではない"),
        ("```\n### コード内\n```\n### 外", "```\n### コード内\n```\n## 外"),
        ("   ### 字下げ3", "   ## 字下げ3"),
        ("文中の ### は変えない", "文中の ### は変えない"),
        ("### A\r\n#### B\r\n", "## A\r\n### B\r\n"),
        ("", ""),
    ],
)
def test_heading_fix(before, after):
    assert heading.fix(before) == after


def test_heading_fix_runs_once_and_handles_none():
    once = heading.fix("#### B")
    assert once == "### B"
    assert heading.fix(None) == ""
