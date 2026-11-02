# 日本語の全角記号（（）、：など）は意図した表記なので、紛らわしい文字の警告は外す
# ruff: noqa: RUF001, RUF002, RUF003
"""公開内容チェック: issue・PR・コメントの本文に、外へ出してはいけない内容が無いかを見る。

当たった文字そのものは報告に書かない。規則の名前・行番号・件数だけを返す。
ここにある規則は汎用の初期値で、正式な一覧は依頼元から受け取って差し替える前提。
禁止語は環境変数 REPOBOT_FORBIDDEN_PATTERNS（1行1正規表現・非公開の secret）から足す。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

TITLE = "題"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    label: str
    patterns: tuple[re.Pattern[str], ...]
    # 同じ行に揃って現れないと当たりにしない組み（例: 会社名と金額）
    requires: tuple[re.Pattern[str], ...] = field(default_factory=tuple)

    def matches(self, line: str) -> int:
        if any(not r.search(line) for r in self.requires):
            return 0
        return sum(len(p.findall(line)) for p in self.patterns)


def _c(*patterns: str, flags: int = 0) -> tuple[re.Pattern[str], ...]:
    # re.ASCII: 日本語の文字を「単語の文字」と見なさない。そうしないと「連絡はtaro@…」のように
    # 日本語と英数字が続いた所で \b が効かず、見逃す
    return tuple(re.compile(p, flags | re.ASCII) for p in patterns)


# GitHub が workflow へ自動で渡す、公開して問題の無い名前
_PUBLIC_SECRET_NAMES = {"GITHUB_TOKEN", "GH_TOKEN", "ACTIONS_RUNTIME_TOKEN"}
_SECRET_NAME = re.compile(
    r"\b(?:[A-Z][A-Z0-9_]*_)?(?:SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|APIKEY|PRIVATE_KEY|ACCESS_KEY)(?:_[A-Z0-9_]*)?\b",
    re.ASCII,
)
_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})(?![A-Za-z0-9-])"
)
# 個人に届かない送り先（GitHub の noreply、文書用の例示ドメイン、git の接続先 git@ホスト）
_NON_PERSONAL_LOCAL = re.compile(r"^(?:git|no-?reply)$", re.IGNORECASE)
_NON_PERSONAL_DOMAIN = re.compile(
    r"(?:^|\.)(?:users\.noreply\.github\.com|noreply\.github\.com|example\.(?:com|org|net)|example)$",
    re.IGNORECASE,
)

RULES: tuple[Rule, ...] = (
    Rule(
        "secret-value",
        "秘密の値",
        _c(
            r"\bAKIA[0-9A-Z]{16}\b",
            r"\bgh[pousr]_[A-Za-z0-9]{36,}\b",
            r"\bgithub_pat_[A-Za-z0-9_]{22,}\b",
            r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b",
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
            r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}\b",
            r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}\b",
            r"\bAIza[0-9A-Za-z_-]{35}\b",
            r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
        )
        + _c(
            # 値は英字と数字の両方を含むものだけ（「token: 200000 まで」や「pwd: /home/…」を拾わない）
            r"(?<![A-Za-z0-9])(?:password|passwd|pwd|secret|token|api[_-]?key|パスワード)\s*[:=：]\s*['\"]?"
            r"(?=[^\s'\"]*[0-9])(?=[^\s'\"]*[A-Za-z])[A-Za-z0-9+/=_.!@#$%^&*~-]{6,}",
            flags=re.IGNORECASE,
        ),
    ),
    Rule("secret-name", "秘密の名前", ()),  # 下の _secret_names で数える
    Rule(
        "attack-procedure",
        "弱点や攻め方の手順",
        _c(
            r"(?:攻撃|悪用|侵入|突破|バイパス)(?:の)?(?:手順|方法|やり方)",
            r"脆弱性.{0,40}(?:手順|再現|ペイロード|悪用)",
            r"インジェクション.{0,40}(?:ペイロード|手順)",
            r"\b(?:exploit|proof[- ]of[- ]concept|PoC)\b.{0,40}\b(?:payload|reproduce)\b",
            r"\b(?:sql ?injection|xss|ssrf|rce)\b.{0,40}\b(?:payload|bypass)\b",
            flags=re.IGNORECASE,
        ),
    ),
    Rule(
        "database",
        "データベースの名前とID",
        _c(
            r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb|rediss?|mssql|sqlserver|sqlite)(?:\+[a-z0-9]+)?://\S+",
            r"(?:\b(?:db|database)|データベース)[ _-]?(?:name|id|名)\s*[:=：]\s*\S+",
            flags=re.IGNORECASE,
        ),
    ),
    Rule(
        "customer-amount",
        "顧客の名前と金額",
        _c(r"[¥￥$]\s?\d[\d,]*|\d[\d,.]*\s?(?:円|万円|億円|ドル|USD|JPY)"),
        requires=_c(
            # 「様」は「仕様」「同様」などを除く
            r"株式会社|有限会社|合同会社|[(（]株[)）]|㈱|商事|御中|顧客|取引先|社(?:に|へ|から|の|様)|(?<![仕同多模異])様|\bInc\.|\bLtd\.|\bcustomer\b",
            flags=re.IGNORECASE,
        ),
    ),
    Rule("personal-email", "個人のメールアドレス", ()),  # 下の _personal_emails で数える
)

MAX_CHUNK = 1000
FORBIDDEN_ID = "forbidden-word"
FORBIDDEN_LABEL = "指定の禁止語"
LABELS = {r.rule_id: r.label for r in RULES} | {FORBIDDEN_ID: FORBIDDEN_LABEL}


def _secret_names(line: str) -> int:
    return sum(1 for m in _SECRET_NAME.finditer(line) if m.group(0) not in _PUBLIC_SECRET_NAMES)


def _personal_emails(line: str) -> int:
    return sum(
        1
        for m in _EMAIL.finditer(line)
        if not _NON_PERSONAL_DOMAIN.search(m.group(1))
        and not _NON_PERSONAL_LOCAL.match(m.group(0).split("@", 1)[0])
    )


def load_forbidden(raw: str | None) -> tuple[list[re.Pattern[str]], int]:
    """禁止語の一覧（1行1正規表現・# で始まる行は注釈）を読む。読めなかった行の数も返す。"""
    patterns: list[re.Pattern[str]] = []
    broken = 0
    for line in (raw or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        try:
            patterns.append(re.compile(s, re.IGNORECASE))
        except re.error:
            broken += 1
    return patterns, broken


@dataclass(frozen=True)
class Hit:
    rule_id: str
    place: str  # "題" か 行番号（1 始まり）の文字列
    count: int


def scan(
    title: str | None, body: str | None, forbidden: list[re.Pattern[str]] | None = None
) -> list[Hit]:
    """題と本文を1行ずつ見て、当たった規則・場所・件数を返す（当たった文字は返さない）。"""
    lines: list[tuple[str, str]] = []
    if title:
        lines.append((TITLE, title))
    for i, line in enumerate((body or "").splitlines(), start=1):
        # とても長い1行は区切って見る（悪意のある長い行で検査を何分も止めないため）
        for j in range(0, max(len(line), 1), MAX_CHUNK):
            lines.append((str(i), line[j : j + MAX_CHUNK]))
    hits: list[Hit] = []
    for place, line in lines:
        for rule in RULES:
            if rule.rule_id == "secret-name":
                n = _secret_names(line)
            elif rule.rule_id == "personal-email":
                n = _personal_emails(line)
            else:
                n = rule.matches(line)
            if n:
                hits.append(Hit(rule.rule_id, place, n))
        n = sum(len(p.findall(line)) for p in forbidden or [])
        if n:
            hits.append(Hit(FORBIDDEN_ID, place, n))
    return hits


def summarize(hits: list[Hit]) -> list[tuple[str, list[str], int]]:
    """規則ごとに (規則名, 場所の一覧, 件数合計) へまとめる。規則の並びは定義順。"""
    order = [r.rule_id for r in RULES] + [FORBIDDEN_ID]
    out = []
    for rule_id in order:
        mine = [h for h in hits if h.rule_id == rule_id]
        if mine:
            places = list(dict.fromkeys(h.place for h in mine))
            out.append((LABELS[rule_id], places, sum(h.count for h in mine)))
    return out


def _place_text(places: list[str]) -> str:
    return "、".join("題" if p == TITLE else f"{p}行目" for p in places)


def report(target: str, hits: list[Hit]) -> str:
    """コメント用の本文。当たった文字そのものは載せない。"""
    if not hits:
        return f"**公開内容チェック: OK**\n\n{target}に、外へ出してはいけない内容は見つかりませんでした。"
    rows = "\n".join(
        f"| {label} | {_place_text(places)} | {count} |" for label, places, count in summarize(hits)
    )
    return (
        f"**公開内容チェック: 要確認**\n\n"
        f"{target}に、公開リポジトリへ書いてはいけない内容が含まれている可能性があります。"
        f"該当箇所を書いた人が直すか消してください（このチェックは本文を自動で編集・削除しません）。\n\n"
        f"| 当たった規則 | 場所 | 件数 |\n| --- | --- | --- |\n{rows}\n\n"
        f"当たった文字そのものは、ここには書いていません。"
    )
