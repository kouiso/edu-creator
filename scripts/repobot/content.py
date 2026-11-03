# 日本語の全角記号（（）、：など）は意図した表記なので、紛らわしい文字の警告は外す
# ruff: noqa: RUF001, RUF002, RUF003
"""公開内容チェック: issue・PR・コメントの本文に、外へ出してはいけない内容が無いかを見る。

当たった文字そのものは報告に書かない。規則の名前・行番号・件数だけを返す。
ここにある規則は汎用の初期値で、正式な一覧は依頼元から受け取って差し替える前提。
禁止語は環境変数 REPOBOT_FORBIDDEN_PATTERNS（1行1正規表現・非公開の secret）から足す。
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

TITLE = "題"
HIDDEN = "非表示"

# とても長い1行は、重ねながら区切って見る（悪意のある長い行で検査を何分も止めないため）。
# 重ねる幅より長い1つの当たり（鍵など）は無いので、区切り目にまたがっても見逃さない
CHUNK = 1000
OVERLAP = 200


def _c(*patterns: str, flags: int = 0) -> tuple[re.Pattern[str], ...]:
    # re.ASCII: 日本語の文字を「単語の文字」と見なさない。そうしないと「連絡はtaro@…」のように
    # 日本語と英数字が続いた所で \b が効かず、見逃す
    return tuple(re.compile(p, flags | re.ASCII) for p in patterns)


# ---- 秘密の名前 ----

# 下線を含む名前だけ（「TOKEN 数」のような普通の言葉は拾わない）
_SECRET_NAME = re.compile(
    r"\b(?:[A-Z][A-Z0-9]*_)*(?:SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|APIKEY|PRIVATE_KEY|ACCESS_KEY)"
    r"(?:_[A-Z0-9]+)*\b",
    re.ASCII,
)
# GitHub が workflow へ自動で渡す、公開して問題の無い名前
_ALWAYS_PUBLIC_NAMES = frozenset({"GITHUB_TOKEN", "GH_TOKEN", "ACTIONS_RUNTIME_TOKEN"})
_TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".sh",
    ".txt",
    ".json",
    ".example",
    ".cfg",
}


# 名前に TOKEN などを含んでも秘密ではない、よくある言葉（LLM の特別な記号・上限・数・公開前提の名前）
_ORDINARY_NAME = re.compile(
    r"^(?:BOS|EOS|PAD|UNK|SEP|CLS|MASK|START|END|STOP)_TOKENS?$"
    r"|(?:^|_)TOKENS?_(?:LIMIT|LIMITS|COUNT|COUNTS|LEN|LENGTH|ID|IDS|TYPE|USAGE|BUDGET)$"
    r"|^NEXT_PUBLIC_|_(?:PATH|FILE|DIR|NAME|ENV)$",
    re.ASCII,
)


def _secret_like(name: str) -> bool:
    return "_" in name and not _ORDINARY_NAME.search(name)


def public_names(root: str | Path = ".") -> frozenset[str]:
    """リポに既に公開されている秘密の名前（例: README に書いた環境変数名）。

    名前そのものは既に誰でも読めるので、本文に書いても新しく漏れたことにはならない。
    """
    root = Path(root)
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files"], capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return _ALWAYS_PUBLIC_NAMES
    names = set(_ALWAYS_PUBLIC_NAMES)
    for rel in out.splitlines():
        # テストの作り物と、この検査自身の規則の文字列は「公開済みの名前」に数えない
        if rel.startswith(("tests/", "scripts/repobot/")):
            continue
        path = root / rel
        if path.suffix not in _TEXT_SUFFIXES and not path.name.startswith(".env"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        names.update(m.group(0) for m in _SECRET_NAME.finditer(text))
    return frozenset(names)


# ---- 個人のメールアドレス ----

_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.([A-Za-z]{2,}))"
    r"(?![A-Za-z0-9-])"
)
# 人が使う送り先の末尾（`q@k.transpose` のようなコードの行列積を拾わないため、知っている末尾に限る）
_MAIL_TLDS = frozenset(
    [
        "com",
        "net",
        "org",
        "jp",
        "io",
        "co",
        "me",
        "dev",
        "app",
        "ai",
        "info",
        "biz",
        "edu",
        "gov",
        "us",
        "uk",
        "de",
        "fr",
        "cn",
        "kr",
        "tw",
        "hk",
        "sg",
        "au",
        "ca",
        "in",
        "nl",
        "se",
        "ch",
        "it",
        "es",
        "br",
        "ru",
        "mobi",
        "name",
        "xyz",
        "cloud",
        "tech",
        "email",
        "mail",
    ]
)
# 個人に届かない送り先（GitHub の noreply、文書用の例示ドメイン、git の接続先 git@ホスト）
_NON_PERSONAL_DOMAIN = re.compile(
    r"(?:^|\.)(?:users\.noreply\.github\.com|noreply\.github\.com)$|(?:^|\.)example(?:\.|$)",
    re.IGNORECASE,
)
_NON_PERSONAL_LOCAL = re.compile(r"^(?:git|no-?reply)$", re.IGNORECASE)


# ---- 規則 ----


@dataclass(frozen=True)
class Rule:
    rule_id: str
    label: str
    patterns: tuple[re.Pattern[str], ...] = ()
    # 同じ行に揃って現れないと当たりにしない組み（例: 会社名と金額）。行全体で見る
    requires: tuple[re.Pattern[str], ...] = ()
    # この言葉が同じ行にあれば当たりにしない（例: 「XSS 対策」のような守る側の話）。行全体で見る
    excludes: tuple[re.Pattern[str], ...] = ()

    def applies_to(self, line: str) -> bool:
        return all(r.search(line) for r in self.requires) and not any(
            e.search(line) for e in self.excludes
        )

    def starts(self, text: str, public: frozenset[str]) -> list[int]:
        """当たった位置（文字の番号）。"""
        if self.rule_id == "secret-name":
            return [
                m.start()
                for m in _SECRET_NAME.finditer(text)
                if _secret_like(m.group(0)) and m.group(0) not in public
            ]
        if self.rule_id == "personal-email":
            return [
                m.start()
                for m in _EMAIL.finditer(text)
                if m.group(2).lower() in _MAIL_TLDS
                and not _NON_PERSONAL_DOMAIN.search(m.group(1))
                and not _NON_PERSONAL_LOCAL.match(m.group(0).split("@", 1)[0])
            ]
        return [m.start() for p in self.patterns for m in p.finditer(text)]


RULES: tuple[Rule, ...] = (
    Rule(
        "secret-value",
        "秘密の値",
        _c(
            r"\bAKIA[0-9A-Z]{16}(?![0-9A-Z])",
            r"\bgh[pousr]_[A-Za-z0-9]{36,}",
            r"\bgithub_pat_[A-Za-z0-9_]{22,}",
            r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
            r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}",
            r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}",
            r"\bAIza[0-9A-Za-z_-]{35}",
            r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        )
        + _c(
            # 値は英字と数字の両方を含むものだけ。版番号（v1.2.3）と場所（/tmp/…）は値と見なさない
            # パスワードは8文字以上、鍵やトークンは16文字以上（「token=gpt4o-mini」のような例を拾わない）
            r"(?<![A-Za-z0-9])(?:password|passwd|pwd|パスワード)\s*[:=：]\s*['\"]?"
            r"(?!v?\d+(?:\.\d+)+(?![A-Za-z0-9]))(?![/.~])"
            r"(?=[^\s'\"]*[0-9])(?=[^\s'\"]*[A-Za-z])[A-Za-z0-9+/=_.!@#$%^&*~-]{8,}",
            # 名前の前に何が付いても（aws_secret_access_key・SECRET_KEY など）、長い値なら値として数える。
            # 名前が公開済みでも、値は秘密のまま
            # 前後に付く語は数を区切る（長い名前のような入力で検査が遅くならないように）
            r"(?<![A-Za-z0-9])(?:[A-Za-z0-9]{1,30}[_-]){0,4}"
            r"(?:secret|token|api[_-]?key|access[_-]?key|private[_-]?key)"
            r"(?:[_-][A-Za-z0-9]{1,30}){0,3}\s*[:=：]\s*['\"]?"
            r"(?![/.~])(?=[^\s'\"]*[0-9])(?=[^\s'\"]*[A-Za-z])[A-Za-z0-9+/=_.!@#$%^&*~-]{16,}",
            flags=re.IGNORECASE,
        ),
    ),
    Rule("secret-name", "秘密の名前"),
    Rule(
        "attack-procedure",
        "弱点や攻め方の手順",
        _c(
            r"(?:攻撃|悪用|侵入|突破|バイパス)(?:する)?(?:手順|方法|やり方)",
            r"脆弱性.{0,20}(?:悪用|ペイロード|攻撃手順|再現手順|手順で(?:再現|悪用))",
        ),
    ),
    # ペイロードの話は守る側（対策・防止）の文脈なら外す。ただし同じ行に「回避・突破」があれば攻める話として数える
    Rule(
        "attack-procedure",
        "弱点や攻め方の手順",
        _c(
            r"インジェクション.{0,40}ペイロード",
            r"\b(?:exploit|proof[- ]of[- ]concept|PoC)\b.{0,40}\bpayload\b",
            r"\b(?:sql ?injection|xss|ssrf|rce)\b.{0,40}\bpayload\b",
            flags=re.IGNORECASE,
        ),
        excludes=_c(
            r"^(?!.*(?:回避|バイパス|突破|すり抜け|\bbypass|\bevad|\bcircumvent))"
            r".*(?:対策|防ぐ|防止|防御|\bmitigat|\bprevent)",
            flags=re.IGNORECASE,
        ),
    ),
    Rule(
        "database",
        "データベースの名前とID",
        _c(
            # 手元の練習用（localhost・127.0.0.1・:memory:）は除く
            r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb|rediss?|mssql|sqlserver|sqlite)(?:\+[a-z0-9]+)?://"
            r"(?!(?:[^@\s/]*@)?(?:localhost|127\.0\.0\.1|\[::1\])(?![A-Za-z0-9.-]))(?!/?:memory:)(?!/\.{1,2}/)\S+",
            # 型の注釈（db_name: str）は値ではない
            r"(?:\b(?:db|database)|データベース)[ _-]?(?:name|id|名)\s*[:=：]\s*"
            r"(?!(?:str|int|Optional|None|Any)\b)\S+",
            flags=re.IGNORECASE,
        ),
    ),
    Rule(
        "customer-amount",
        "顧客の名前と金額",
        _c(r"[¥￥$]\s?\d[\d,]*|\d[\d,.]*\s?(?:円|万円|億円|ドル|USD|JPY)"),
        requires=_c(
            # 「会社の」「各社の」「この様に」「仕様」などの普通の言葉は除く
            r"株式会社|有限会社|合同会社|[(（]株[)）]|㈱|商事|御中|顧客|取引先"
            r"|(?<![会各自他本弊御貴当])社(?:に|へ|から|様)"
            r"|(?<![仕同多模異こそあどの客者])様(?![子々式相])|\bcustomer\b",
            flags=re.IGNORECASE,
        ),
    ),
    Rule("personal-email", "個人のメールアドレス"),
)

FORBIDDEN_ID = "forbidden-word"
FORBIDDEN_LABEL = "指定の禁止語"
LABELS = {r.rule_id: r.label for r in RULES} | {FORBIDDEN_ID: FORBIDDEN_LABEL}

# 禁止語の一覧は grep -E 用に書かれている（scripts/guard/check-forbidden.sh と共用）ので、
# POSIX の文字クラスを Python の書き方へ直してから使う
_POSIX_CLASSES = {
    "[:alpha:]": "a-zA-Z",
    "[:digit:]": "0-9",
    "[:alnum:]": "a-zA-Z0-9",
    "[:upper:]": "A-Z",
    "[:lower:]": "a-z",
    "[:space:]": r"\s",
    "[:blank:]": r" \t",
    "[:punct:]": r"!-/:-@\[-`{-~",
    "[:xdigit:]": "0-9A-Fa-f",
}


def load_forbidden(raw: str | None) -> tuple[list[re.Pattern[str]], int]:
    """禁止語の一覧（1行1正規表現・# で始まる行は注釈）を読む。読めなかった行の数も返す。"""
    patterns: list[re.Pattern[str]] = []
    broken = 0
    for line in (raw or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        for posix, py in _POSIX_CLASSES.items():
            s = s.replace(posix, py)
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


def _chunked_starts(text: str, find: Callable[[str], Iterable[int]]) -> set[int]:
    """長い行を区切って探し、当たった位置を行全体の番号で返す。

    区切りごとに前後へ OVERLAP 文字の文脈を付けて探し、その区切りの持ち分で始まる当たりだけ数える。
    こうすると区切り目でも \\b や前後の判定が行全体と同じになり、1つの当たりを二重に数えない。
    """
    if len(text) <= CHUNK:
        return set(find(text))
    found: set[int] = set()
    step = CHUNK - OVERLAP
    for j in range(0, len(text), step):
        left = max(0, j - OVERLAP)
        window = text[left : j + CHUNK]
        last = j + CHUNK >= len(text)
        for s in find(window):
            pos = left + s
            if pos >= j and (last or pos < j + step):
                found.add(pos)
        if last:
            break
    return found


def scan(
    title: str | None,
    body: str | None,
    forbidden: list[re.Pattern[str]] | None = None,
    public: frozenset[str] = _ALWAYS_PUBLIC_NAMES,
) -> list[Hit]:
    """題と本文を1行ずつ見て、当たった規則・場所・件数を返す（当たった文字は返さない）。"""
    lines: list[tuple[str, str]] = []
    if title:
        lines.append((TITLE, title))
    # 行番号は GitHub の表示と同じく改行（\n）だけで数える
    for i, line in enumerate((body or "").split("\n"), start=1):
        lines.append((str(i), line.rstrip("\r")))
    pats = forbidden or []
    hits: list[Hit] = []
    for place, line in lines:
        for rule in RULES:
            if not rule.applies_to(line):
                continue
            n = len(_chunked_starts(line, lambda t, r=rule: r.starts(t, public)))
            if n:
                hits.append(Hit(rule.rule_id, place, n))
        n = len(_chunked_starts(line, lambda t: [m.start() for p in pats for m in p.finditer(t)]))
        if n:
            hits.append(Hit(FORBIDDEN_ID, place, n))
    return hits


def summarize(hits: list[Hit]) -> list[tuple[str, list[str], int]]:
    """規則ごとに (規則名, 場所の一覧, 件数合計) へまとめる。規則の並びは定義順。

    禁止語の場所は出さない。出すと、書き換えを繰り返して非公開の一覧を当てられてしまうため。
    """
    # 同じ規則名の行を2つに分けた規則があるので、重ねずに定義順で並べる
    order = list(dict.fromkeys([r.rule_id for r in RULES] + [FORBIDDEN_ID]))
    out = []
    for rule_id in order:
        mine = [h for h in hits if h.rule_id == rule_id]
        if mine:
            if rule_id == FORBIDDEN_ID:
                places = [HIDDEN]
            else:
                places = list(dict.fromkeys(h.place for h in mine))
            out.append((LABELS[rule_id], places, sum(h.count for h in mine)))
    return out


MAX_PLACES = 20


def _place_text(places: list[str]) -> str:
    def one(p: str) -> str:
        if p == TITLE:
            return "題"
        if p == HIDDEN:
            return "（非表示）"
        return f"{p}行目"

    # コメントは 65536 文字までなので、場所は先頭の数件だけ出す
    shown = "、".join(one(p) for p in places[:MAX_PLACES])
    if len(places) > MAX_PLACES:
        shown += f" ほか{len(places) - MAX_PLACES}か所"
    return shown


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
