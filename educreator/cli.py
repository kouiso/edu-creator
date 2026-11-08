"""edu-creator 3.0 のコマンド。

今ある段: auth（login / status）、spec（check）、lessons（check）。
plan・design・stage・write・gate・package などは WBS の順（A3〜A13）で足す。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from educreator import __version__


def _cmd_auth(args: argparse.Namespace) -> int:
    from educreator.accounts import AccountError, load_accounts
    from educreator.auth import login, status_report

    try:
        cfg = load_accounts(Path(args.config) if args.config else None)
        if args.auth_cmd == "login":
            return login(cfg.get(args.provider, args.account))
        print(status_report(cfg))
        return 0
    except AccountError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 2


def _cmd_spec(args: argparse.Namespace) -> int:
    from pydantic import ValidationError

    from educreator.spec import check_chapters, load_spec

    path = Path(args.path)
    try:
        spec = load_spec(path)
    except (ValidationError, ValueError) as e:
        print(f"{path}: スキーマに合わない\n{e}", file=sys.stderr)
        return 1
    problems = check_chapters(spec, path.parent)
    for p in problems:
        print(p)
    print(f"{path}: {'OK' if not problems else f'{len(problems)} 件の食い違い'}")
    return 1 if problems else 0


def _cmd_lessons(args: argparse.Namespace) -> int:
    from educreator.lessons import check_lessons, load_lessons

    path = Path(args.path)
    problems = check_lessons(load_lessons(path))
    for p in problems:
        print(p)
    print(f"{path}: {'OK' if not problems else f'{len(problems)} 件'}")
    return 1 if problems else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="edu-creator", description="教材を作る道具（edu-creator 3.0）")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("auth", help="サブスクのアカウントにログインする・状態を見る")
    cfg_opt = argparse.ArgumentParser(add_help=False)
    cfg_opt.add_argument(
        "--config", help="edu-creator.toml のパス（省略時はカレントから上へ探し、無ければ既定）"
    )
    asub = a.add_subparsers(dest="auth_cmd", required=True)
    al = asub.add_parser(
        "login", parents=[cfg_opt], help="CLI のログインを、そのアカウントの置き場で起動する"
    )
    al.add_argument("--provider", choices=["claude", "chatgpt"], required=True)
    al.add_argument("--account", default="personal-1")
    asub.add_parser(
        "status", parents=[cfg_opt], help="アカウントごと・CLI ごとのログインと使用量の窓"
    )
    a.set_defaults(func=_cmd_auth)

    s = sub.add_parser("spec", help="course-spec.yaml を検査する")
    ssub = s.add_subparsers(dest="spec_cmd", required=True)
    sc = ssub.add_parser("check", help="スキーマと、章立てと実ファイルの一致を確かめる")
    sc.add_argument("path", nargs="?", default="course-spec.yaml")
    s.set_defaults(func=_cmd_spec)

    lessons = sub.add_parser("lessons", help="学び台帳を検査する（E-7）")
    lsub = lessons.add_subparsers(dest="lessons_cmd", required=True)
    lc = lsub.add_parser("check")
    lc.add_argument("path", nargs="?", default="knowledge/lessons.yaml")
    lessons.set_defaults(func=_cmd_lessons)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
