"""design の段（A13）。ルートの定義から画面の直積表（ルート × 役割 × 状態）を作り、R-1 の空きマスを数える。

ルートの集め方はスタックで違うので、stack profile の routes で切り替える:
- `decorator-routes`: ルートのファイルの `@<bp>.route(...)` を AST で読む（アプリを起動しないので Python の版に依らない）。
  画面のテンプレートは関数の中の最初の `render_template("...")`
- `page-files`: App Router の `page.tsx` から道を作る（`(group)` は道に入れず、`[id]` は `<id>` にする）。`route.ts` は画面を持たない

役割ごとの振る舞いは、教材ごとに人がガードを読んで書く（course-spec の design.access。書式は下の cell）。
書いていないマスは「要確認」として空きマスに数える。R-1 は空きマス0件と、要デザインのマスがすべてデザインで埋まること。
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

DEFAULT_ROLES = [
    ("admin", "管理者"),
    ("owner", "作成者"),
    ("member", "メンバー"),
    ("outsider", "非メンバー"),
    ("anon", "未ログイン"),
]
DEFAULT_STATES = [
    ("empty", "空"),
    ("normal", "通常"),
    ("error", "エラー"),
    ("denied", "権限なし"),
    ("loading", "読み込み中"),
]
NEED = "**要デザイン**"
BLANK = "要確認（役割の振る舞いが未記入）"
NA_REASON = {
    "empty": "該当なし（一覧や0件の表示を持たない）",
    "error": "該当なし（入力が無い。例外は共通のエラー画面）",
    "loading": "該当なし（ページ全体を読み直す）",
}


@dataclass(frozen=True)
class Route:
    endpoint: str
    rules: tuple[str, ...]
    methods: tuple[str, ...]
    screen: str | None
    source: str


def _template_of(
    fn: ast.FunctionDef, helpers: dict[str, ast.FunctionDef], depth: int = 0
) -> str | None:
    """関数が出す画面のテンプレート。直接の render_template が無ければ、同じファイルの関数の呼び出しを1段たどる。"""
    calls: list[str] = []
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if (
            node.func.id == "render_template"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            return str(node.args[0].value)
        if node.func.id in helpers and node.func.id != fn.name:
            calls.append(node.func.id)
    if depth == 0:
        for name in calls:
            t = _template_of(helpers[name], helpers, depth + 1)
            if t:
                return t
    return None


def _decorator_routes(root: Path) -> list[Route]:
    out: list[Route] = []
    for f in sorted(root.glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        bps: dict[str, tuple[str, str]] = {}
        for n in tree.body:
            if (
                isinstance(n, ast.Assign)
                and isinstance(n.value, ast.Call)
                and isinstance(n.value.func, ast.Name)
                and n.value.func.id == "Blueprint"
                and isinstance(n.targets[0], ast.Name)
            ):
                prefix = next(
                    (ast.literal_eval(k.value) for k in n.value.keywords if k.arg == "url_prefix"),
                    "",
                )
                bps[n.targets[0].id] = (ast.literal_eval(n.value.args[0]), prefix)
        # 同じファイルの補助関数（`_render_task_list` など）を経由して画面を出すルートがあるので、関数ごとの画面を先に作る
        helpers = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        for fn in tree.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            rules: list[str] = []
            methods: tuple[str, ...] = ("GET",)
            bp = ""
            for d in fn.decorator_list:
                if (
                    isinstance(d, ast.Call)
                    and isinstance(d.func, ast.Attribute)
                    and d.func.attr == "route"
                    and isinstance(d.func.value, ast.Name)
                    and d.func.value.id in bps
                ):
                    bp, prefix = bps[d.func.value.id]
                    rules.append(prefix + ast.literal_eval(d.args[0]))
                    for k in d.keywords:
                        if k.arg == "methods":
                            methods = tuple(ast.literal_eval(k.value))
            if not rules:
                continue
            screen = _template_of(fn, helpers)
            out.append(Route(f"{bp}.{fn.name}", tuple(rules), methods, screen, f.name))
    return out


def _page_file_routes(root: Path) -> list[Route]:
    out: list[Route] = []
    for f in sorted(list(root.rglob("page.tsx")) + list(root.rglob("route.ts"))):
        parts = [
            p
            for p in f.relative_to(root).parent.parts
            if not (p.startswith("(") and p.endswith(")"))
        ]
        path = "/" + "/".join(re.sub(r"^\[(?:\.\.\.)?(.+)\]$", r"<\1>", p) for p in parts)
        is_page = f.name == "page.tsx"
        out.append(
            Route(
                path if is_page else f"api:{path}",
                (path,),
                ("GET",) if is_page else ("API",),
                f.relative_to(root).as_posix() if is_page else None,
                f.relative_to(root).as_posix(),
            )
        )
    return out


def discover(kind: str, root: Path) -> list[Route]:
    if kind == "decorator-routes":
        return _decorator_routes(root)
    if kind == "page-files":
        return _page_file_routes(root)
    raise ValueError(f"ルートの集め方 '{kind}' は無い（decorator-routes か page-files）")


def cell(role_rule: str | None, state: str, states: list[str]) -> tuple[str, str]:
    """(表に書く文字, 種類)。種類は need（要デザイン）・na（該当なし）・blank（空き）。

    役割の書き方: show / show:<補足> / deny:<転送先> / 403 / login / na:<理由>
    """
    if role_rule is None:
        return BLANK, "blank"
    kind, _, note = role_rule.partition(":")
    if kind == "show":
        if state == "normal":
            return NEED + (f"（{note}）" if note else ""), "need"
        if state == "denied":
            m = re.search(r"それ以外は deny:(\S+)", note)
            if m:
                return f"条件に合わない人は転送先 `{m.group(1)}` の flash（error）で表す", "na"
            return "該当なし（この役割は見られる）", "na"
        if state in states:
            return NEED, "need"
        return NA_REASON.get(state, f"該当なし（{state}）"), "na"
    if kind == "deny":
        if state == "denied":
            return f"転送先 `{note}` の flash（error）で表す", "na"
        return "該当なし（画面に入れない）", "na"
    if kind == "403":
        if state == "denied":
            return "共通のエラー画面（403）で表す", "na"
        return "該当なし（画面に入れない）", "na"
    if kind == "login":
        if state == "denied":
            return "ログイン画面へ転送（warning の flash）で表す", "na"
        return "該当なし（ログイン画面へ転送）", "na"
    if kind == "na":
        return f"該当なし（{note}）", "na"
    raise ValueError(f"役割の書き方が違う: {role_rule!r}")


@dataclass
class Matrix:
    markdown: str
    stats: dict[str, int] = field(default_factory=dict)


class AccessRoute(BaseModel):
    """役割ごとの振る舞い（course-spec の design.access の1ルート）。書式は cell。"""

    model_config = ConfigDict(extra="forbid")

    endpoint: str
    roles: dict[str, str] = Field(default_factory=dict)
    states: list[str] = Field(default_factory=list)


class Access(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routes: list[AccessRoute] = Field(default_factory=list)


def build(routes: list[Route], access: dict[str, Any] | None) -> Matrix:
    # 形が違えば KeyError や AttributeError の traceback ではなく、ValueError（cli が報告する）にする
    try:
        parsed = Access.model_validate(access or {})
    except ValidationError as e:
        raise ValueError(f"design.access の形が違う: {e}") from e
    by_ep = {r.endpoint: r for r in parsed.routes}
    unknown = sorted(set(by_ep) - {r.endpoint for r in routes})
    if unknown:
        raise ValueError(f"役割の振る舞いに、コードに無いルートがある: {unknown}")
    screens = [r for r in routes if r.screen]
    counts = {"need": 0, "na": 0, "blank": 0}
    blocks = []
    for r in screens:
        a = by_ep.get(r.endpoint, AccessRoute(endpoint=r.endpoint))
        roles = a.roles
        lines = [
            f"### `{r.endpoint}` — {', '.join(f'`{x}`' for x in r.rules)}（{'・'.join(r.methods)}）",
            "",
            f"画面: `{r.screen}`",
            "",
            "| 役割 | " + " | ".join(s for _, s in DEFAULT_STATES) + " |",
            "|---|" + "---|" * len(DEFAULT_STATES),
        ]
        for rk, rname in DEFAULT_ROLES:
            row = []
            for sk, _ in DEFAULT_STATES:
                text, kind = cell(roles.get(rk), sk, a.states)
                row.append(text)
                counts[kind] += 1
            lines.append(f"| {rname} | " + " | ".join(row) + " |")
        blocks.append("\n".join(lines))
    stats = {
        "rules": sum(len(r.rules) for r in routes),
        "endpoints": len(routes),
        "screens": len(screens),
        "screen_files": len({r.screen for r in screens}),
        "cells": sum(counts.values()),
        "need": counts["need"],
        "na": counts["na"],
        "blank": counts["blank"],
    }
    head = [
        "# 画面の直積表（R-1）",
        "",
        "> 生成物（`edu-creator design matrix`）。役割の振る舞いは course-spec の design.access を直す。",
        "",
        "| 項目 | 数 |",
        "|---|---|",
        f"| ルール | {stats['rules']} |",
        f"| エンドポイント | {stats['endpoints']} |",
        f"| 画面を持つエンドポイント | {stats['screens']} |",
        f"| 直積のマス | {stats['cells']} |",
        f"| 要デザイン | {stats['need']} |",
        f"| 該当なし（理由付き） | {stats['na']} |",
        f"| 空きマス（要確認） | {stats['blank']} |",
        "",
        "## 画面を持たないルート",
        "",
    ]
    head += [
        f"- `{r.endpoint}`（{'・'.join(r.methods)}、{r.source}）" for r in routes if not r.screen
    ]
    head += ["", "## 画面ごとの直積", ""]
    return Matrix("\n".join(head) + "\n" + "\n\n".join(blocks) + "\n", stats)


def load_access(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    return dict(json.loads(path.read_text(encoding="utf-8")))
