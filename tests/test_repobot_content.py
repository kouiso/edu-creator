# 日本語の全角記号（（）、：など）は意図した表記なので、紛らわしい文字の警告は外す
# ruff: noqa: RUF001, RUF002, RUF003
"""公開内容チェック（scripts/repobot/content.py）のテスト。

秘密らしい値はテスト用の作り物で、gitleaks や禁止語検査に当たらないよう実行時に組み立てる。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from repobot import content


def ids(hits):
    return sorted({h.rule_id for h in hits})


# 作り物の値（ソースに完全な形を書かない）
FAKE_AWS = "AKIA" + "Q" * 16
FAKE_GH = "ghp" + "_" + "a1" * 18
FAKE_PAT = "github" + "_pat_" + "B" * 30
FAKE_SLACK = "xox" + "b-" + "1234567890-abcdef"
FAKE_PEM = "-----BEGIN " + "RSA PRIVATE KEY-----"
FAKE_SK = "sk" + "-ant-" + "x" * 30
FAKE_GOOGLE = "AIza" + "S" * 35
FAKE_JWT = "eyJ" + "h" * 12 + "." + "p" * 12 + "." + "s" * 12
FAKE_ASSIGN = "pass" + "word: " + "zq7" * 3


@pytest.mark.parametrize(
    "line",
    [
        FAKE_AWS,
        FAKE_GH,
        FAKE_PAT,
        FAKE_SLACK,
        FAKE_PEM,
        FAKE_SK,
        FAKE_GOOGLE,
        FAKE_JWT,
        FAKE_ASSIGN,
    ],
)
def test_secret_values_turn_red(line):
    assert "secret-value" in ids(content.scan(None, f"設定はこれ: {line}"))


def test_secret_name_is_flagged_but_public_names_are_not():
    assert ids(content.scan(None, "STRIPE_" + "SECRET_KEY を入れる")) == ["secret-name"]
    assert ids(content.scan(None, "DB_" + "PASSWORD を変える")) == ["secret-name"]
    assert content.scan(None, "workflow では GITHUB_TOKEN と GH_TOKEN を使う") == []


@pytest.mark.parametrize(
    "line",
    [
        "攻撃手順はこう",
        "認証の突破方法を書く",
        "exploit PoC payload: 1. send this",
        "この脆弱性は次の手順で再現できます",
        "SQLインジェクションのペイロードはこれ",
        "SQL injection payload は次の通り",
    ],
)
def test_attack_procedures_turn_red(line):
    assert "attack-procedure" in ids(content.scan(None, line))


@pytest.mark.parametrize(
    "line",
    [
        "接続先 postgres://u:p@db.internal:5432/app",
        "mongodb+srv://cluster0.example/test",
        "DB名: app_prod_main",
        "database_id = 1234abcd",
    ],
)
def test_database_info_turns_red(line):
    assert "database" in ids(content.scan(None, line))


def test_customer_and_amount_need_both_on_one_line():
    assert "customer-amount" in ids(content.scan(None, "株式会社サンプルへの見積は 1,200,000円"))
    assert "customer-amount" in ids(content.scan(None, "customer Foo paid $3000"))
    # 金額だけ、会社名だけでは当たらない
    assert content.scan(None, "サーバ代は月 500円") == []
    assert content.scan(None, "株式会社サンプルと打合せ") == []
    # 「仕様」などの普通の言葉で当たらない
    assert content.scan(None, "仕様では 3 円単位で丸める") == []


def test_personal_email_but_not_noreply_or_examples():
    assert ids(content.scan(None, "連絡は taro.yamada@gmail.com まで")) == ["personal-email"]
    assert content.scan(None, "123+someone@users.noreply.github.com") == []
    assert content.scan(None, "noreply@example.com と user@example.org は例") == []


def test_ordinary_text_is_green():
    body = "## 背景\n画面の表示が遅いので、キャッシュを足す。\n\n## 完了条件\n- [ ] 一覧が1秒以内に出る\n"
    assert content.scan("一覧表示を速くする", body) == []


def test_title_is_scanned_and_reported_as_title():
    hits = content.scan(f"鍵 {FAKE_AWS}", "本文は普通")
    assert [(h.rule_id, h.place) for h in hits] == [("secret-value", content.TITLE)]


def test_line_numbers_and_counts():
    body = "1行目は普通\nmail a@corp.co.jp and b@corp.co.jp\n3行目\nc@corp.co.jp"
    summary = content.summarize(content.scan(None, body))
    assert summary == [("個人のメールアドレス", ["2", "4"], 3)]


def test_forbidden_words_from_secret_list():
    patterns, broken = content.load_forbidden("# 注釈\n\nprojectx\nfoo[0-9]+\n(broken\n")
    assert broken == 1
    assert len(patterns) == 2
    hits = content.scan(None, "ProjectX の件と foo12 の件", patterns)
    assert [(h.rule_id, h.count) for h in hits] == [("forbidden-word", 2)]


def test_forbidden_list_accepts_grep_posix_classes():
    patterns, broken = content.load_forbidden("bar[[:digit:]]+\nbaz[[:space:]]qux")
    assert broken == 0
    hits = content.scan(None, "bar42 と baz qux", patterns)
    assert [(h.rule_id, h.count) for h in hits] == [("forbidden-word", 2)]


def test_forbidden_word_place_is_hidden_so_the_list_cannot_be_probed():
    patterns, _ = content.load_forbidden("projectx")
    text = content.report("この issue", content.scan(None, "a\nb\nProjectX", patterns))
    assert "| 指定の禁止語 | （非表示） | 1 |" in text
    assert "3行目" not in text


def test_load_forbidden_handles_none_and_empty():
    assert content.load_forbidden(None) == ([], 0)
    assert content.load_forbidden("") == ([], 0)


def test_report_never_contains_the_matched_text():
    secret_line = f"key {FAKE_GH} mail taro.yamada@gmail.com"
    hits = content.scan(None, secret_line)
    text = content.report("この issue", hits)
    assert "要確認" in text
    assert FAKE_GH not in text
    assert "taro.yamada" not in text
    assert "| 秘密の値 | 1行目 | 1 |" in text
    assert "| 個人のメールアドレス | 1行目 | 1 |" in text


def test_report_ok_when_clean():
    assert "公開内容チェック: OK" in content.report("この issue", [])


def test_none_body_is_safe():
    assert content.scan(None, None) == []


def test_japanese_next_to_ascii_is_still_caught():
    assert ids(content.scan(None, "連絡はtaro.yamada@gmail.comまで")) == ["personal-email"]
    assert ids(content.scan(None, f"鍵は{FAKE_AWS}です")) == ["secret-value"]
    assert ids(content.scan(None, "データベース名: app_main")) == ["database"]
    assert ids(content.scan(None, "DB ID: 42")) == ["database"]


@pytest.mark.parametrize(
    "line",
    [
        "エラーの回避方法を書く",
        "pass" + "word: 未設定のまま",
        "token: 必要に応じて",
        "secret の名前は FORBIDDEN_PATTERNS",
    ],
)
def test_common_wording_is_not_flagged(line):
    assert content.scan(None, line) == []


FAKE_STRIPE = "sk" + "_live_" + "Z" * 24


@pytest.mark.parametrize(
    "line, rule",
    [
        (FAKE_STRIPE, "secret-value"),
        ("db_" + "password=hunter2pass", "secret-value"),
        ("パスワード: hunter2pass", "secret-value"),
        ("SECRET" + "_KEY を設定", "secret-name"),
        ("API" + "_KEY を入れる", "secret-name"),
        ("postgresql+asyncpg://u:p@h/app", "database"),
        ("rediss://cache.internal:6380", "database"),
        ("sqlite:///data/app.db", "database"),
        ("ABC社に500万円", "customer-amount"),
        ("(株)山田 300万円", "customer-amount"),
        ("山田商事様 300万円", "customer-amount"),
    ],
)
def test_previously_missed_cases_turn_red(line, rule):
    assert rule in ids(content.scan(None, line))


@pytest.mark.parametrize(
    "line",
    [
        "git clone git@github.com:kouiso/edu-creator.git",
        "Co-Authored-By: Claude <noreply@anthropic.com>",
        "token: 200000 まで",
        "Token = abcdef の上限",
        "pwd: /srv/app/work",
        "Fix XSS in markdown preview (steps below)",
        "the API client costs $5/month",
        "仕様では 500円 単位",
    ],
)
def test_ordinary_text_stays_green(line):
    assert content.scan(None, line) == []


def test_very_long_line_is_scanned_quickly_and_still_caught():
    import time

    line = "顧客 " + "1," * 30000 + " " + FAKE_GH
    start = time.monotonic()
    hits = content.scan(None, line)
    assert time.monotonic() - start < 5
    assert "secret-value" in ids(hits)


@pytest.mark.parametrize(
    "line",
    [
        "OPENAI_API_KEYが設定されていません",
        "TOKEN 数が上限",
        "各社の API 料金は $3〜$15",
        "会社の予算で $20",
        "この様に $5 かかる",
        "scores = q@k.transpose(-2, -1)",
        "x@self.weight.T",
        "pkg@git.example.dev",
        "脆弱性を再現するテストを追加",
        "脆弱性の報告手順は SECURITY.md",
        "XSS bypass を防ぐため escape",
        "PoC で reproduce できた",
        "pwd: /tmp/out1",
        "secret: v1.2.3",
        "token: v2.0.1",
        "db_name: str",
        "sqlite:///:memory:",
        "redis://localhost:6379",
        "postgres://user:pw@127.0.0.1:5432/app",
    ],
)
def test_ordinary_repo_text_stays_green(line):
    public = frozenset({"OPENAI_API_KEY"})
    assert content.scan(None, line, public=public) == []


def test_public_names_come_from_tracked_files(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "README.md").write_text("OPENAI_API_KEY と HF_TOKEN を設定", encoding="utf-8")
    (tmp_path / "bin.dat").write_bytes(b"STRIPE_SECRET_KEY")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    names = content.public_names(tmp_path)
    assert {"OPENAI_API_KEY", "HF_TOKEN", "GITHUB_TOKEN"} <= names
    assert "STRIPE_SECRET_KEY" not in names  # 文字のファイル以外は見ない
    assert content.scan(None, "HF_TOKEN を入れる", public=names) == []
    assert ids(content.scan(None, "NEW_SERVICE" + "_TOKEN を入れる", public=names)) == [
        "secret-name"
    ]


def test_public_names_outside_git_falls_back(tmp_path):
    assert content.public_names(tmp_path / "missing") == frozenset(
        {"GITHUB_TOKEN", "GH_TOKEN", "ACTIONS_RUNTIME_TOKEN"}
    )


@pytest.mark.parametrize("offset", [0, 790, 799, 800, 990, 995, 999, 1000, 1601, 2500])
def test_key_across_chunk_boundary_is_found_once(offset):
    line = "x " * (offset // 2) + ("x" if offset % 2 else "") + " " + FAKE_AWS + " end"
    hits = content.scan(None, line)
    assert [(h.rule_id, h.count) for h in hits] == [("secret-value", 1)]


def test_line_numbers_follow_github_newlines_only():
    body = "a\u2028b\x0cc\n" + FAKE_AWS + "\r\nend"
    assert [h.place for h in content.scan(None, body)] == ["2"]


def test_chunk_starts_keep_word_context():
    # 区切り目（800文字ごと）でも、行全体で見た時と同じ判定になる
    mid_word = "x" * 799 + "Z" + FAKE_AWS + " " + "y" * 400
    assert content.scan(None, mid_word) == []
    long_local = "a " * 395 + "abcdefghijklmnopqrst@gmail.com " + "b" * 600
    assert [(h.rule_id, h.count) for h in content.scan(None, long_local)] == [("personal-email", 1)]
    straddle = "x" * 797 + " AWS_SECRET_ACCESS_KEY " + "y" * 400
    assert content.scan(None, straddle, public=frozenset({"AWS_SECRET_ACCESS_KEY"})) == []


def test_company_and_amount_far_apart_on_one_long_line():
    line = "株式会社テスト " + "x" * 3000 + " 100万円"
    assert ids(content.scan(None, line)) == ["customer-amount"]


@pytest.mark.parametrize(
    "line",
    [
        "BOS_TOKEN と EOS_TOKEN と PAD_TOKEN",
        "TOKEN_LIMIT と TOKEN_COUNT と MAX_TOKENS",
        "PRIVATE_KEY_PATH を指定",
        "NEXT_PUBLIC_API_KEY は公開前提",
        "コストは $0.003 / 1K tokens。お客様向け",
        "モデル様式は 3ドル",
        "ご担当者様 3,000円",
        "sqlite:///./data.db",
        "token: abc123 は例です",
        "token=gpt4o-mini",
        "XSS 対策として payload をエスケープ",
    ],
)
def test_llm_tutorial_wording_stays_green(line):
    assert content.scan(None, line) == []


def test_generic_names_are_flagged_with_the_real_repo_list():
    # 本番と同じく、このリポの公開済みの名前を使っても、一般的な秘密の名前は当たる
    public = content.public_names(Path(__file__).resolve().parent.parent)
    for name in ("SECRET" + "_KEY", "API" + "_KEY", "PRIVATE" + "_KEY", "DB" + "_PASSWORD"):
        assert ids(content.scan(None, f"{name} を設定", public=public)) == ["secret-name"], name
    assert "NEW_SERVICE" + "_TOKEN" not in public


def test_report_caps_places_to_stay_under_comment_limit():
    body = "\n".join("taro.yamada@gmail.com" for _ in range(30000))
    text = content.report("この issue", content.scan(None, body))
    assert "ほか29980か所" in text
    assert len(text) < 65536


@pytest.mark.parametrize(
    "line",
    [
        "サニタイズを回避する攻撃手順: 1. 送る",
        "攻撃手順（防御側の視点は後述）: 1. 送る",
        "SQL injection payload to bypass escaping: x OR 1=1",
        "XSS payload: <script>x</script> bypasses the sanitizer",
        "XSS 対策をすり抜ける payload はこれ",
    ],
)
def test_attack_write_ups_are_caught_even_with_defence_words(line):
    assert "attack-procedure" in ids(content.scan(None, line))


def test_split_attack_rule_reports_one_row():
    hits = content.scan(None, "攻撃手順はこれ\nexploit payload はこれ")
    assert content.summarize(hits) == [("弱点や攻め方の手順", ["1", "2"], 2)]


@pytest.mark.parametrize(
    "line",
    [
        "aws_secret" + "_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCY1",
        "SECRET" + "_KEY=django-insecure-a8f7sd9f8a7sdf98a7sdf",
        "PRIVATE" + "_KEY=0x4c0883a69102937d6231471b5dbb6204fe512961",
    ],
)
def test_long_values_are_caught_even_when_the_name_is_public(line):
    public = frozenset({"SECRET_KEY", "PRIVATE_KEY", "AWS_SECRET_ACCESS_KEY"})
    assert "secret-value" in ids(content.scan(None, line, public=public))


def test_bypass_method_wording_is_caught():
    assert ids(content.scan(None, "エスケープをバイパスする方法")) == ["attack-procedure"]


@pytest.mark.parametrize("line", ["x_secret_" * 7000 + ":", "a_" * 32000 + "=", "A_" * 32000])
def test_name_shaped_long_input_is_fast(line):
    import time

    start = time.monotonic()
    content.scan(None, line)
    assert time.monotonic() - start < 5
