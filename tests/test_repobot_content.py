# 日本語の全角記号（（）、：など）は意図した表記なので、紛らわしい文字の警告は外す
# ruff: noqa: RUF002, RUF003
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
