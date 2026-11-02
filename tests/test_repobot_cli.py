"""repobot の入口（イベント → API 呼び出し・終了コード）と workflow 定義のテスト。

GitHub には繋がず、偽の API（FakeGitHub）で呼び出しを記録して確かめる。
"""

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from repobot import __main__ as cli  # noqa: E402
from repobot import triage  # noqa: E402
from repobot.api import GitHubError, upsert_comment  # noqa: E402

REPO = "owner/repo"
FAKE_MAIL = "taro.yamada" + "@gmail.com"


class FakeGitHub:
    """呼ばれた API を記録する偽物。fail に (method, path の一部) を入れるとその呼び出しで失敗する。"""

    def __init__(self, comments=None, files=None, fail=()):
        self.repo = REPO
        self.comments = comments or []
        self.files = files or []
        self.fail = fail
        self.calls = []

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        for m, part in self.fail:
            if m == method and part in path:
                raise GitHubError(403, path, "forbidden")
        return {}

    def paginate(self, path):
        self.calls.append(("GET", path, None))
        if path.endswith("/comments"):
            return self.comments
        if path.endswith("/files"):
            return self.files
        return []

    def writes(self):
        return [c for c in self.calls if c[0] != "GET"]


def issue_event(body, title="題", action="opened", login="alice", labels=None):
    return {
        "action": action,
        "issue": {
            "number": 5,
            "title": title,
            "body": body,
            "user": {"login": login, "type": "Bot" if login.endswith("[bot]") else "User"},
            "labels": labels or [],
        },
    }


def pr_event(body, action="opened", ref="feature/x", login="alice", draft=False):
    return {
        "action": action,
        "pull_request": {
            "number": 9,
            "title": "PR",
            "body": body,
            "draft": draft,
            "head": {"ref": ref},
            "user": {"login": login, "type": "Bot" if login.endswith("[bot]") else "User"},
        },
    }


# ---- 公開内容チェック ----


def test_content_red_posts_one_marked_comment_without_matched_text():
    gh = FakeGitHub()
    rc = cli.run_content("issues", issue_event(f"連絡先 {FAKE_MAIL}"), gh, {})
    assert rc == 1
    [(method, path, body)] = gh.writes()
    assert (method, path) == ("POST", f"/repos/{REPO}/issues/5/comments")
    assert body["body"].startswith("<!-- repobot:public-content:body -->")
    assert "個人のメールアドレス" in body["body"]
    assert "taro.yamada" not in body["body"]


def test_content_green_posts_nothing_when_never_red():
    gh = FakeGitHub()
    assert cli.run_content("issues", issue_event("普通の文章です"), gh, {}) == 0
    assert gh.writes() == []


def test_content_fixed_updates_previous_comment_to_ok():
    old = {"id": 77, "body": "<!-- repobot:public-content:body -->\n要確認"}
    gh = FakeGitHub(comments=[old])
    assert cli.run_content("issues", issue_event("直した", action="edited"), gh, {}) == 0
    [(method, path, body)] = gh.writes()
    assert (method, path) == ("PATCH", f"/repos/{REPO}/issues/comments/77")
    assert "公開内容チェック: OK" in body["body"]


@pytest.mark.parametrize(
    "event_name, event, number, marker",
    [
        (
            "issue_comment",
            {"issue": {"number": 3}, "comment": {"id": 41, "body": FAKE_MAIL, "html_url": "u"}},
            3,
            "comment-41",
        ),
        (
            "pull_request_review_comment",
            {"pull_request": {"number": 9}, "comment": {"id": 42, "body": FAKE_MAIL, "html_url": "u"}},
            9,
            "review-comment-42",
        ),
        ("pull_request_target", pr_event(FAKE_MAIL), 9, "body"),
    ],
)
def test_content_covers_comments_reviews_and_prs(event_name, event, number, marker):
    gh = FakeGitHub()
    assert cli.run_content(event_name, event, gh, {}) == 1
    [(method, path, body)] = gh.writes()
    assert path == f"/repos/{REPO}/issues/{number}/comments"
    assert f"<!-- repobot:public-content:{marker} -->" in body["body"]


def test_content_uses_forbidden_list_from_env():
    gh = FakeGitHub()
    env = {"REPOBOT_FORBIDDEN_PATTERNS": "secretproject"}
    assert cli.run_content("issues", issue_event("SecretProject の話"), gh, env) == 1
    assert "指定の禁止語" in gh.writes()[0][2]["body"]


def test_content_skips_own_comments():
    gh = FakeGitHub()
    event = {"issue": {"number": 3}, "comment": {"id": 1, "body": "<!-- repobot:format -->\nx " + FAKE_MAIL}}
    assert cli.run_content("issue_comment", event, gh, {}) == 0
    assert gh.calls == []


def test_content_still_red_when_comment_cannot_be_written():
    gh = FakeGitHub(fail=[("POST", "/comments")])
    assert cli.run_content("issues", issue_event(FAKE_MAIL), gh, {}) == 1


def test_content_ignores_other_events():
    assert cli.run_content("push", {}, FakeGitHub(), {}) == 0


# ---- 書き方チェック ----

GOOD_ISSUE = "## 背景\na\n## 今どこまで\nb\n## 次にやること\nc\n## 誰の判断待ち\nd\n## 完了条件\n- [ ] e\n"


def test_form_red_then_green_updates_the_same_comment():
    gh = FakeGitHub()
    assert cli.run_form("issues", issue_event("## 背景\na"), gh, {}) == 1
    [(method, _, body)] = gh.writes()
    assert method == "POST" and body["body"].startswith(cli.FORM_MARKER)

    gh2 = FakeGitHub(comments=[{"id": 8, "body": body["body"]}])
    assert cli.run_form("issues", issue_event(GOOD_ISSUE, action="edited"), gh2, {}) == 0
    [(method, path, body2)] = gh2.writes()
    assert (method, path) == ("PATCH", f"/repos/{REPO}/issues/comments/8")
    assert "書き方チェック: OK" in body2["body"]


def test_form_same_result_does_not_repost():
    gh = FakeGitHub()
    cli.run_form("issues", issue_event("## 背景\na"), gh, {})
    posted = gh.writes()[0][2]["body"]
    gh2 = FakeGitHub(comments=[{"id": 8, "body": posted}])
    assert cli.run_form("issues", issue_event("## 背景\na", action="edited"), gh2, {}) == 1
    assert gh2.writes() == []


def test_form_green_without_previous_comment_posts_nothing():
    gh = FakeGitHub()
    assert cli.run_form("issues", issue_event(GOOD_ISSUE), gh, {}) == 0
    assert gh.writes() == []


def test_form_pr_red_and_green():
    gh = FakeGitHub()
    assert cli.run_form("pull_request_target", pr_event("## 概要\nx"), gh, {}) == 1
    good = "## 概要\nx\n## 変更内容\n- y\n## 関連Issue\nRefs #6\n"
    assert cli.run_form("pull_request_target", pr_event(good), FakeGitHub(), {}) == 0


@pytest.mark.parametrize(
    "event_name, event",
    [
        ("pull_request_target", pr_event("", draft=True)),
        ("pull_request_target", pr_event("", login="dependabot[bot]")),
        ("issues", issue_event("", login="github-actions[bot]")),
        ("issues", issue_event("", labels=[{"name": "alert"}])),
        ("issues", issue_event("", title="[SBI] 分解")),
        ("push", {}),
    ],
)
def test_form_skips_excluded(event_name, event):
    gh = FakeGitHub()
    assert cli.run_form(event_name, event, gh, {}) == 0
    assert gh.calls == []


# ---- 見出し修正 ----


def test_heading_patches_only_when_changed():
    gh = FakeGitHub()
    assert cli.run_heading("issues", issue_event("### 背景\na"), gh, {}) == 0
    assert gh.writes() == [("PATCH", f"/repos/{REPO}/issues/5", {"body": "## 背景\na"})]
    gh2 = FakeGitHub()
    assert cli.run_heading("issues", issue_event("## 背景\na"), gh2, {}) == 0
    assert gh2.calls == []
    assert cli.run_heading("pull_request_target", pr_event("### x"), gh2, {}) == 0
    assert gh2.calls == []


# ---- 担当者とラベル ----


def test_triage_assigns_author_and_adds_labels():
    gh = FakeGitHub(files=[{"filename": "README.md"}, {"filename": "uv.lock"}, {"filename": "core/a.py"}])
    assert cli.run_triage("pull_request_target", pr_event("", ref="fix/bug"), gh, {}) == 0
    assert gh.writes() == [
        ("POST", f"/repos/{REPO}/issues/9/assignees", {"assignees": ["alice"]}),
        ("POST", f"/repos/{REPO}/issues/9/labels", {"labels": ["bugfix", "documentation", "dependencies"]}),
    ]


def test_triage_skips_bot_assignment_but_labels():
    gh = FakeGitHub(files=[{"filename": "pyproject.toml"}])
    cli.run_triage("pull_request_target", pr_event("", ref="dependabot/uv/x", login="dependabot[bot]"), gh, {})
    assert gh.writes() == [("POST", f"/repos/{REPO}/issues/9/labels", {"labels": ["dependencies"]})]


def test_triage_continues_when_assignment_fails():
    gh = FakeGitHub(files=[{"filename": "tests/test_a.py"}], fail=[("POST", "/assignees")])
    assert cli.run_triage("pull_request_target", pr_event("", ref="chore/x"), gh, {}) == 0
    assert gh.writes()[-1] == ("POST", f"/repos/{REPO}/issues/9/labels", {"labels": ["chore", "test"]})


def test_triage_synchronize_does_not_reassign_and_no_labels_means_no_call():
    gh = FakeGitHub(files=[{"filename": "core/a.py"}])
    cli.run_triage("pull_request_target", pr_event("", action="synchronize", ref="claude/x"), gh, {})
    assert gh.writes() == []


@pytest.mark.parametrize(
    "branch, label",
    [
        ("feature/a", "feature"),
        ("feat/a", "feature"),
        ("bugfix/a", "bugfix"),
        ("fix/a", "bugfix"),
        ("hotfix/a", "hotfix"),
        ("chore/a", "chore"),
        ("refactor/a", "chore"),
        ("docs/a", "documentation"),
        ("release/1.0", "release"),
        ("Feature/A", "feature"),
        ("develop", None),
        ("fixture-update", None),
        (None, None),
    ],
)
def test_branch_label(branch, label):
    assert triage.branch_label(branch) == label


def test_path_labels_follow_repo_layout():
    paths = ["docs/a.md", "config/x.yaml", ".github/workflows/ci.yml", "test_integration.py", ".mise.toml"]
    assert triage.path_labels(paths) == ["documentation", "dependencies", "config", "ci", "test"]
    assert triage.labels_for("docs/x", ["a.md"]) == ["documentation"]


# ---- 目印つきコメント ----


def test_upsert_comment_paths():
    gh = FakeGitHub(comments=[{"id": 1, "body": "他の人のコメント"}])
    assert upsert_comment(gh, 2, "<!-- m -->", "x", create_if_missing=False) == "skipped"
    assert upsert_comment(gh, 2, "<!-- m -->", "x") == "created"
    gh2 = FakeGitHub(comments=[{"id": 3, "body": "<!-- m -->\nx"}])
    assert upsert_comment(gh2, 2, "<!-- m -->", "x") == "unchanged"
    assert upsert_comment(gh2, 2, "<!-- m -->", "y") == "updated"


# ---- 入口 ----


def test_main_reads_event_file(tmp_path):
    path = tmp_path / "event.json"
    path.write_text(json.dumps(issue_event("### 背景\na")), encoding="utf-8")
    env = {"GITHUB_EVENT_PATH": str(path), "GITHUB_EVENT_NAME": "issues", "GITHUB_REPOSITORY": REPO}
    gh = FakeGitHub()
    assert cli.main(["heading"], env=env, client=gh) == 0
    assert gh.writes()[0][0] == "PATCH"
    assert cli.main([], env=env, client=gh) == 2
    assert cli.main(["unknown"], env=env, client=gh) == 2


def test_module_runs_as_script(tmp_path):
    import subprocess

    path = tmp_path / "event.json"
    path.write_text(json.dumps({"action": "opened"}), encoding="utf-8")
    env = {
        "GITHUB_EVENT_PATH": str(path),
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REPOSITORY": REPO,
        "PYTHONPATH": str(ROOT / "scripts"),
        "PATH": "/usr/bin:/bin",
    }
    res = subprocess.run([sys.executable, "-m", "repobot", "content"], env=env, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


# ---- workflow 定義 ----

WORKFLOWS = ROOT / ".github" / "workflows"
REPOBOT_WORKFLOWS = {
    "public-content-check.yml": "content",
    "issue-pr-format-check.yml": "form",
    "issue-heading-fix.yml": "heading",
    "pr-triage.yml": "triage",
}


def load(name):
    with open(WORKFLOWS / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("name, command", sorted(REPOBOT_WORKFLOWS.items()))
def test_repobot_workflows_run_only_default_branch_code(name, command):
    wf = load(name)
    for job in wf["jobs"].values():
        steps = job["steps"]
        checkout = [s for s in steps if str(s.get("uses", "")).startswith("actions/checkout@")]
        assert checkout, name
        assert checkout[0]["with"]["ref"] == "${{ github.event.repository.default_branch }}"
        assert checkout[0]["with"]["persist-credentials"] is False
        runs = [s["run"] for s in steps if "run" in s]
        assert runs == [f"python3 -m repobot {command}"]
        # 書いた人の文字列を run に埋め込まない（式展開による命令の差し込みを防ぐ）
        assert all("${{" not in r for r in runs)


def test_workflow_permissions_are_minimal():
    for name in REPOBOT_WORKFLOWS:
        perms = load(name)["permissions"]
        assert set(perms) <= {"contents", "issues", "pull-requests"}
        assert perms["contents"] == "read"


def test_workflow_triggers_cover_the_issue_scope():
    # PyYAML は on を True と読む
    on = lambda n: load(n)[True]  # noqa: E731
    assert set(on("public-content-check.yml")) == {
        "issues",
        "issue_comment",
        "pull_request_target",
        "pull_request_review_comment",
    }
    assert set(on("issue-pr-format-check.yml")) == {"issues", "pull_request_target"}
    assert on("issue-heading-fix.yml") == {"issues": {"types": ["opened"]}}
    assert set(on("pr-triage.yml")["pull_request_target"]["types"]) == {"opened", "reopened", "synchronize"}


def test_dependabot_config_matches_the_issue():
    with open(ROOT / ".github" / "dependabot.yml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assert cfg["version"] == 2
    assert {u["package-ecosystem"] for u in cfg["updates"]} == {"uv", "github-actions"}
    for u in cfg["updates"]:
        assert u["schedule"] == {"interval": "monthly", "time": "09:00", "timezone": "Asia/Tokyo"}
        assert u["cooldown"] == {"default-days": 3}
        assert u["open-pull-requests-limit"] == 2
        assert u["groups"]["minor-patch"] == {"applies-to": "version-updates", "update-types": ["minor", "patch"]}


def test_auto_merge_only_for_grouped_minor_patch():
    wf = load("dependabot-auto-merge.yml")
    job = wf["jobs"]["auto-merge"]
    assert job["if"] == "github.event.pull_request.user.login == 'dependabot[bot]'"
    merge = job["steps"][1]
    assert "dependency-group == 'minor-patch'" in merge["if"]
    assert "semver-major" in merge["if"]
    assert "${{" not in merge["run"]


def test_issue_form_requires_the_five_sections():
    with open(ROOT / ".github" / "ISSUE_TEMPLATE" / "request.yml", encoding="utf-8") as f:
        tpl = yaml.safe_load(f)
    fields = [b for b in tpl["body"] if b["type"] == "textarea"]
    assert [b["attributes"]["label"] for b in fields] == list(cli.form.ISSUE_SECTIONS)
    assert all(b["validations"]["required"] for b in fields)
