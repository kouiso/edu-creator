#!/usr/bin/env python3
"""check_tech_stack.py（Flask 版）の退行テスト。

テストの無いチェッカーは、検出が一度も動いていなくても誰も気づかない（移植元で
check_tone.py に実例がある）。壊れたら落ちる形で振る舞いを固定する。

見るのは次の4つ。
  1. 禁止パターン全件に検出例があること（SAMPLES が forbidden_patterns を覆う）
  2. 検査しない言語だけが飛ばされること
  3. Flask 判定と警告の出方
  4. 誤検知しないこと（地の文・別の語に含まれる文字列）

1 は本体の関数内ローカル変数が相手なので import できない。ソースを AST で読んで突き合わせる。
"""

import ast
import io
import re
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "educreator" / "checks" / "qa"))

import check_tech_stack as checker  # noqa: E402

CHECKER_PATH = Path(checker.__file__)
FAIL_LINE = '❌ 技術スタックチェックFAIL'
WARN_LINE = '⚠️ Flask パターンが検出されませんでした'

EXPECTED_SKIPPED_LANGS = frozenset({'mermaid', 'bash', 'shell', 'sh', 'text', 'console'})

# 禁止パターン1件につき検出例を2つ（書き方を変えたもの）。1つだけだと、正規表現を
# その1件だけ通る形に狭めてもテストが素通りする。
SAMPLES: list[tuple[str, str, str]] = [
    ('Django', 'python', 'from django.db import models'),
    ('Django', 'python', 'import django'),
    ('FastAPI', 'python', 'from fastapi import FastAPI'),
    ('FastAPI', 'python', '    import fastapi'),
    ('Bottle', 'python', 'from bottle import route'),
    ('Bottle', 'python', 'import bottle'),
    ('Tornado', 'python', 'import tornado.web'),
    ('Tornado', 'python', 'from tornado import ioloop'),
    ('Pyramid', 'python', 'from pyramid.config import Configurator'),
    ('Pyramid', 'python', 'import pyramid'),
    ('# type: ignore', 'python', 'x: int = "a"  # type: ignore'),
    ('# type: ignore', 'python', 'y = f()  #type:ignore[assignment]'),
    ('# noqa', 'python', 'import os  # noqa'),
    ('# noqa', 'python', 'from app import *  # noqa: F403'),
    ('jQuery', 'html', '<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>'),
    ('jQuery', 'jinja', '<script defer src="/static/jquery.js"></script>'),
    ('Chart.js', 'html', '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'),
    ('Chart.js', 'jinja', '<script src="/static/chart.umd.min.js"></script>'),
    ('D3.js', 'html', '<script src="https://d3js.org/d3.v7.min.js"></script>'),
    ('D3.js', 'html', '<script src="/static/d3.js"></script>'),
]

# 検出してはいけないもの。
NON_DETECTION: list[tuple[str, str]] = [
    ('python', 'from flask import Flask'),
    ('python', 'djangoish_name = 1'),
    ('python', '# type の話をするコメント'),
    ('jinja', '{# jQuery は使いません #}'),
    ('html', '<p>Chart.js は使わず表で示します</p>'),
]


def fence(lang: str, code: str) -> str:
    return f'```{lang}\n{code}\n```\n'


def run(text: str) -> tuple[bool, list[str]]:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'day05_x.md'
        p.write_text(text, encoding='utf-8')
        buf = io.StringIO()
        with redirect_stdout(buf):
            ok = checker.check_tech_stack(str(p))
    return ok, buf.getvalue().splitlines()


def declared_names() -> list[str]:
    # 禁止パターンは stack profile の qa.tech_stack.forbidden にある。検査が読み込んだ一覧をそのまま見る
    return [name for _pattern, name in checker.FORBIDDEN]


def main() -> int:
    failed = 0
    total = 0

    # 1. 全パターンに検出例が2つずつあるか
    names = declared_names()
    total += 1
    if not names:
        failed += 1
        print('  ❌ forbidden_patterns を読み取れない')
    for name in names:
        total += 1
        if sum(1 for n, _, _ in SAMPLES if n == name) < 2:
            failed += 1
            print(f'  ❌ 検出例が2つ無いパターン: {name}')

    # 1b. 検出例が本当に FAIL になり、その名前で報告されるか
    for name, lang, code in SAMPLES:
        total += 1
        ok, lines = run(fence(lang, code))
        if ok or f'❌ 技術の範囲外: {name}' not in lines:
            failed += 1
            print(f'  ❌ 検出されない: {name} / {code!r} → {lines}')

    # 2. 検査しない言語の固定と、その言語では飛ばされること
    total += 1
    if frozenset(checker.SKIPPED_LANGS) != EXPECTED_SKIPPED_LANGS:
        failed += 1
        print(f'  ❌ 検査しない言語が変わった: {sorted(checker.SKIPPED_LANGS)}')
    for lang in sorted(EXPECTED_SKIPPED_LANGS):
        total += 1
        ok, _ = run(fence(lang, 'from django.db import models'))
        if not ok:
            failed += 1
            print(f'  ❌ {lang} のブロックを検査している')

    # 3. Flask 判定と警告
    total += 3
    ok, lines = run(fence('python', 'from flask import Blueprint'))
    if not ok or WARN_LINE in lines:
        failed += 1
        print(f'  ❌ Flask の import で警告が出た: {lines}')
    ok, lines = run(fence('jinja', '{% extends "base.html" %}'))
    if not ok or WARN_LINE in lines:
        failed += 1
        print(f'  ❌ Jinja の extends を Flask と判定しない: {lines}')
    ok, lines = run(fence('python', 'print("hello")'))
    if not ok or WARN_LINE not in lines:
        failed += 1
        print(f'  ❌ Flask の無い日に警告が出ない、または FAIL した: {lines}')

    # 4. 誤検知
    for lang, code in NON_DETECTION:
        total += 1
        ok, lines = run(fence(lang, code))
        if not ok or any(line.startswith('❌ 技術の範囲外') for line in lines):
            failed += 1
            print(f'  ❌ 誤検知: {code!r} → {lines}')

    # 5. 同じ違反を2ブロックで書いても1件
    total += 1
    _, lines = run(fence('python', 'import django') + fence('python', 'from django import forms'))
    if sum(1 for line in lines if re.match(r'^❌ 技術の範囲外: Django$', line)) != 1:
        failed += 1
        print(f'  ❌ 同じ違反が重複して報告された: {lines}')

    if failed:
        print(f'❌ check_tech_stack 自己テスト {failed}/{total} 失敗')
        return 1
    print(f'✅ check_tech_stack 自己テスト {total}/{total} 合格')
    return 0


if __name__ == '__main__':
    sys.exit(main())
