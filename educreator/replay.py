"""写経リプレイ（A4・G1）。Day ごとのツリーを取り出し、入れて・起動して・画面が返るかを確かめる。

以前の写経ゲートは「落ちないこと」を合格にしていたので、DB のポートを間違えても SKIP が exit 0 で緑になった（G1）。
ここでは SKIP を作らない。Day のツリーが無い、起動しない、決めた時間内に応答しない、期待と違う状態コードを返す、
のどれも不合格にする。

Day のツリーの取り出し元は2つ:
- git のタグ（`day-{nn}-end` のような書式）。Day ごとに一時的な worktree を作って取り出す
- Day ごとのフォルダ（`dist/day-snapshots/day{nn}` のような書式）。そのまま使う

起動とアクセスのしかたは stack profile（install・start・url・ready_path）から取る。`{port}` は空いているポートに置き換える。
Day ごとに確かめる道は course-spec の qa.replay_paths（{Day: {道: 期待する状態コード}}）で足せる。
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass, field
from email.message import Message
from pathlib import Path
from typing import IO, Any

from educreator.profiles import StackProfile


@dataclass(frozen=True)
class DaySource:
    """Day のツリーの取り出し元。kind は git か dirs。pattern は `{nn}`（2桁）か `{n}` を含む。"""

    kind: str
    root: Path
    pattern: str

    def name(self, day: int) -> str:
        return self.pattern.format(nn=f"{day:02d}", n=day)


@dataclass
class DayResult:
    day: int
    ok: bool
    steps: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> DayResult:
        self.ok = False
        self.steps.append(f"❌ {msg}")
        return self


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextlib.contextmanager
def checkout(src: DaySource, day: int) -> Iterator[Path | None]:
    """Day のツリーを取り出す。無ければ None を渡す（呼び出し側が不合格にする）。"""
    name = src.name(day)
    if src.kind == "dirs":
        p = src.root / name
        yield p if p.is_dir() else None
        return
    ok = subprocess.run(
        ["git", "-C", str(src.root), "rev-parse", "--verify", "--quiet", f"refs/tags/{name}"],
        capture_output=True,
        check=False,
    )
    if ok.returncode != 0:
        yield None
        return
    tmp = Path(tempfile.mkdtemp(prefix=f"replay-{day:02d}-"))
    wt = tmp / "tree"
    try:
        subprocess.run(
            ["git", "-C", str(src.root), "worktree", "add", "--detach", "-q", str(wt), name],
            check=True,
            capture_output=True,
        )
        yield wt
    finally:
        subprocess.run(
            ["git", "-C", str(src.root), "worktree", "remove", "--force", str(wt)],
            capture_output=True,
            check=False,
        )
        shutil.rmtree(tmp, ignore_errors=True)


def _fmt(args: list[str], port: int) -> list[str]:
    return [a.replace("{port}", str(port)) for a in args]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # リダイレクトを追うと、未ログインの 302 が転送先の 200 に化けて見える。期待する状態コードは最初の応答で見る
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> urllib.request.Request | None:
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _get(url: str, timeout: float) -> int:
    try:
        with _OPENER.open(url, timeout=timeout) as r:  # 手元の 127.0.0.1 だけを叩く
            return int(r.status)
    except urllib.error.HTTPError as e:
        return int(e.code)


def replay_day(
    profile: StackProfile,
    src: DaySource,
    day: int,
    paths: dict[str, int] | None = None,
    install: bool = True,
    ready_timeout: float = 60.0,
    setup: list[list[str]] | None = None,
    shots: list[dict[str, Any]] | None = None,
    login: dict[str, Any] | None = None,
    shots_dir: Path | None = None,
) -> DayResult:
    res = DayResult(day, ok=True)
    with checkout(src, day) as tree:
        if tree is None:
            return res.fail(f"Day{day:02d} のツリー `{src.name(day)}` が無い")
        if install:
            p = subprocess.run(
                profile.install, cwd=tree, capture_output=True, text=True, check=False
            )
            if p.returncode != 0:
                return res.fail(
                    f"入れられない（{' '.join(profile.install)}）: {(p.stderr or p.stdout).strip()[-300:]}"
                )
            res.steps.append("✅ 入れた")
        for cmd in setup or []:
            p = subprocess.run(cmd, cwd=tree, capture_output=True, text=True, check=False)
            if p.returncode != 0:
                return res.fail(
                    f"準備のコマンドが落ちた（{' '.join(cmd)}）: {(p.stderr or p.stdout).strip()[-300:]}"
                )
            res.steps.append(f"✅ {' '.join(cmd)}")
        port = free_port()
        base = profile.url.replace("{port}", str(port))
        env = {**os.environ, "PORT": str(port)}
        # パイプに溜めたまま誰も読まないと、出力の多いサーバー（開発サーバーなど）が書き込みで止まる。ファイルへ流し、落ちた時に末尾を読む
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as log:
            proc = subprocess.Popen(
                _fmt(profile.start, port),
                cwd=tree,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + ready_timeout
                status = None
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        log.seek(0)
                        out = log.read()
                        return res.fail(
                            f"起動してすぐ止まった（rc={proc.returncode}）: {out.strip()[-300:]}"
                        )
                    try:
                        status = _get(base + profile.ready_path, timeout=2)
                        break
                    except (urllib.error.URLError, ConnectionError, OSError):
                        time.sleep(0.2)
                if status is None:
                    return res.fail(f"{ready_timeout:.0f}秒で {profile.ready_path} が応答しない")
                if status != 200:
                    return res.fail(f"{profile.ready_path} が {status} を返した（200 のはず）")
                res.steps.append(f"✅ 起動して {profile.ready_path} が 200")
                for path, want in (paths or {}).items():
                    try:
                        got = _get(base + path, timeout=5)
                    except (urllib.error.URLError, OSError) as e:
                        res.fail(f"{path} に繋がらない（{want} のはず）: {e}")
                        continue
                    if got != want:
                        res.fail(f"{path} が {got} を返した（{want} のはず）")
                    else:
                        res.steps.append(f"✅ {path} が {want}")
                if shots:
                    shot_dir = (shots_dir or Path(tempfile.gettempdir())) / f"day{day:02d}"
                    for r in take_shots(base, shots, login, shot_dir):
                        if r.get("ok"):
                            res.steps.append(f"✅ 撮影 {r['name']}（{r['status']}）")
                        else:
                            res.fail(
                                f"撮影 {r['name']} が失敗（{r.get('status')}）: {r.get('error', '')}"
                            )
                return res
            finally:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()


SHOOT_JS = Path(__file__).with_name("shoot.cjs")


def take_shots(
    base: str, shots: list[dict[str, Any]], login: dict[str, Any] | None, out: Path
) -> list[dict[str, Any]]:
    """起動中のサーバーから、画面のスクショを撮る（Playwright。配色はライトに固定）。"""
    out.mkdir(parents=True, exist_ok=True)
    payload = {"base": base, "shots": shots, "login": login, "out": str(out)}

    def all_failed(error: str) -> list[dict[str, Any]]:
        return [{"name": s["name"], "ok": False, "status": 0, "error": error} for s in shots]

    try:
        p = subprocess.run(
            ["node", str(SHOOT_JS)],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return all_failed(f"撮影が動かなかった: {type(e).__name__}: {e}")
    if p.returncode != 0:
        return all_failed(p.stderr.strip()[-300:])
    try:
        return list(json.loads(p.stdout))
    except json.JSONDecodeError:
        return all_failed(f"撮影の出力が JSON でない: {p.stdout.strip()[-200:]}")


def parse_days(spec: str, last: int) -> list[int]:
    """`1-3,5` のような指定を Day の一覧にする。"""
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    bad = [d for d in out if d < 1 or d > last]
    if bad:
        raise ValueError(f"Day の番号が範囲（1〜{last}）の外: {bad}")
    return sorted(set(out))
