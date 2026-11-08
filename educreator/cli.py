"""edu-creator 3.0 のコマンド。

今ある段: auth（login / status）、spec（check）、check（教材の検査）、replay（写経リプレイ）、lessons（check）。
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


def _cmd_check(args: argparse.Namespace) -> int:
    from pydantic import ValidationError

    from educreator import checks
    from educreator.spec import load_spec

    if args.list:
        for c in checks.CHECKS:
            print(f"{c.id:<20} {c.summary}")
        return 0
    spec_path = Path(args.spec)
    try:
        spec = load_spec(spec_path)
        config = checks.qa_config(
            spec.stack_profile, spec.qa, spec_path.parent / spec.app_repo, spec.budget.model_dump()
        )
        selected = [checks.get(i) for i in args.ids] if args.ids else list(checks.CHECKS)
    except (ValidationError, ValueError, KeyError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 2
    target = spec_path.parent / spec.material_dir
    failed = 0
    for c in selected:
        r = checks.run_check(c, target, config)
        print(f"{'OK  ' if r.ok else 'FAIL'} {c.id}")
        if not r.ok:
            failed += 1
        # 落ちた検査は1本だけなら出力を出す。-v なら通った検査の出力（budget の表など）も出す
        if args.verbose or (not r.ok and len(selected) == 1):
            print(r.output)
    print(f"{len(selected) - failed}/{len(selected)} 件通過")
    return 1 if failed else 0


def _cmd_replay(args: argparse.Namespace) -> int:
    from pydantic import ValidationError

    from educreator.profiles import load_profile
    from educreator.replay import DaySource, parse_days, replay_day
    from educreator.spec import load_spec

    spec_path = Path(args.spec)
    try:
        spec = load_spec(spec_path)
        if spec.replay is None:
            raise ValueError(f"{spec_path} に replay が無い")
        days = parse_days(args.days or f"1-{spec.days}", spec.days)
    except (ValidationError, ValueError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 2
    profile = load_profile(spec.stack_profile)
    rp = spec.replay
    src = DaySource(rp.kind, spec_path.parent / rp.root, rp.pattern)
    failed = 0
    for d in days:
        r = replay_day(
            profile,
            src,
            d,
            rp.paths.get(d),
            install=rp.install and not args.no_install,
            setup=rp.setup,
            shots=[s.model_dump() for s in rp.shots.get(d, [])],
            login=rp.login.model_dump() if rp.login else None,
            shots_dir=spec_path.parent / rp.shots_dir,
        )
        print(f"{'OK  ' if r.ok else 'FAIL'} Day{d:02d}")
        for s in r.steps:
            if args.verbose or not r.ok:
                print(f"     {s}")
        failed += not r.ok
    print(f"{len(days) - failed}/{len(days)} Day 通過")
    return 1 if failed else 0


def _cmd_judge(args: argparse.Namespace) -> int:
    from pydantic import ValidationError

    from educreator import judge as J
    from educreator.accounts import AccountError, load_accounts
    from educreator.replay import parse_days
    from educreator.spec import load_spec

    spec_path = Path(args.spec)
    try:
        spec = load_spec(spec_path)
        out_dir = spec_path.parent / spec.judge.out_dir
        if args.judge_cmd == "run":
            cfg = load_accounts(Path(args.config) if args.config else None)
            account = cfg.get(args.provider, args.account)
            days = parse_days(args.days, spec.days)
    except (ValidationError, ValueError, AccountError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 2
    if args.judge_cmd == "run":
        mat = spec_path.parent / spec.material_dir
        failed = 0
        for d in days:
            md = next(iter(sorted(mat.glob(f"day{d:02d}_*.md"))), None)
            if md is None:
                print(f"FAIL Day{d:02d}: 本文が無い")
                failed += 1
                continue
            try:
                r = J.judge_day(md, d, account, state_dir=cfg.state_dir)
            except J.JudgeError as e:
                print(f"FAIL {e}")
                failed += 1
                continue
            path = J.save(r, out_dir)
            print(f"OK   Day{d:02d} {r.judge} {r.scores} → {path}")
        return 1 if failed else 0
    reports = J.load_all(out_dir)
    if not reports:
        print(f"{out_dir} に採点が無い")
        return 1
    for dim, _ in J.DIMENSIONS:
        c = J.control_chart(reports, dim)
        flag = (
            "、外れ: " + ", ".join(f"Day{d:02d}({v:.1f})" for d, v in c.out_of_control)
            if c.out_of_control
            else ""
        )
        print(f"{dim:<17} X̄ {c.mean:.2f}  σ {c.sigma:.2f}{flag}")
    problems = J.gate(reports, spec.judge.calibrated)
    print(f"合否に使う次元（較正済み）: {', '.join(spec.judge.calibrated) or 'なし（参考値だけ）'}")
    for p in problems:
        print(f"  ❌ {p}")
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

    c = sub.add_parser("check", help="教材を検査する（A3。stack profile の qa で切り替える）")
    c.add_argument("ids", nargs="*", help="検査の ID（省略で全部）")
    c.add_argument("--spec", default="course-spec.yaml")
    c.add_argument("--list", action="store_true", help="検査の一覧を出す")
    c.add_argument("-v", "--verbose", action="store_true", help="落ちた検査の出力を全部出す")
    c.set_defaults(func=_cmd_check)

    rp = sub.add_parser(
        "replay", help="Day ごとのツリーを入れて起動し、画面が返るかを確かめる（A4）"
    )
    rp.add_argument("--spec", default="course-spec.yaml")
    rp.add_argument("--days", help="1-3,5 のように指定（省略で全 Day）")
    rp.add_argument(
        "--no-install", action="store_true", help="入れる段を飛ばす（入れ済みのツリー）"
    )
    rp.add_argument("-v", "--verbose", action="store_true")
    rp.set_defaults(func=_cmd_replay)

    j = sub.add_parser("judge", help="Day を5つの次元で採点し、管理図と R-6 で見る（A6）")
    jsub = j.add_subparsers(dest="judge_cmd", required=True)
    jr = jsub.add_parser("run", help="Day を採点して reports/judge に残す")
    jr.add_argument("--spec", default="course-spec.yaml")
    jr.add_argument("--days", required=True, help="1-3,5 のように指定")
    jr.add_argument("--provider", choices=["claude", "chatgpt"], default="claude")
    jr.add_argument("--account", default="personal-1")
    jr.add_argument("--config", help="edu-creator.toml のパス")
    js = jsub.add_parser("report", help="残した採点から管理図と R-6 の判定を出す")
    js.add_argument("--spec", default="course-spec.yaml")
    j.set_defaults(func=_cmd_judge)

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
