"""写経リプレイ（A4）のテスト。本物のサーバーを Day ごとのツリーから起動して確かめる。"""

import subprocess
import sys
from pathlib import Path

import pytest

from educreator.profiles import QaConfig, StackProfile
from educreator.replay import DaySource, parse_days, replay_day

SERVER = """
import http.server, sys

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/private":
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        code = 200 if self.path in ("/", "/tasks") else 404
        self.send_response(code)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *a):
        pass

http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
"""

BROKEN = "import sys\nsys.exit('ImportError: no module named app')\n"

PROFILE = StackProfile(
    name="t",
    language="python",
    filepath_comment={".py": "# filepath: {path}"},
    install=[sys.executable, "-c", "print('installed')"],
    start=[sys.executable, "server.py", "{port}"],
    test=[],
    url="http://127.0.0.1:{port}",
    ready_path="/",
    qa=QaConfig(code_langs=["python"], real_prefixes=["app/"]),
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def tagged_repo(tmp_path):
    repo = tmp_path / "reader-tree"
    repo.mkdir()
    _git(repo, "init", "-q")
    for day, body in ((1, SERVER), (2, BROKEN)):
        (repo / "server.py").write_text(body, encoding="utf-8")
        _git(repo, "add", "server.py")
        _git(repo, "commit", "-q", "--no-gpg-sign", "-m", f"day {day}")
        _git(repo, "tag", f"day-{day:02d}-end")
    return repo


def test_good_day_starts_and_answers(tagged_repo):
    paths = {"/tasks": 200, "/nope": 404, "/private": 302}
    r = replay_day(PROFILE, DaySource("git", tagged_repo, "day-{nn}-end"), 1, paths)
    assert r.ok, r.steps
    # /private はリダイレクトを追わずに 302 を見る（追うと転送先の 200 に化ける）
    assert r.steps == [
        "✅ 入れた",
        "✅ 起動して / が 200",
        "✅ /tasks が 200",
        "✅ /nope が 404",
        "✅ /private が 302",
    ]


def test_crashing_server_fails_instead_of_skipping(tagged_repo):
    r = replay_day(PROFILE, DaySource("git", tagged_repo, "day-{nn}-end"), 2)
    assert not r.ok
    assert "起動してすぐ止まった" in r.steps[-1] and "ImportError" in r.steps[-1]


def test_missing_tree_is_a_failure(tagged_repo):
    r = replay_day(PROFILE, DaySource("git", tagged_repo, "day-{nn}-end"), 3)
    assert not r.ok and "day-03-end" in r.steps[-1]


def test_wrong_status_fails(tagged_repo):
    r = replay_day(PROFILE, DaySource("git", tagged_repo, "day-{nn}-end"), 1, {"/tasks": 404})
    assert not r.ok and "/tasks が 200 を返した（404 のはず）" in r.steps[-1]


def test_worktrees_are_cleaned_up(tagged_repo):
    replay_day(PROFILE, DaySource("git", tagged_repo, "day-{nn}-end"), 1)
    out = subprocess.run(
        ["git", "-C", str(tagged_repo), "worktree", "list"], capture_output=True, text=True
    ).stdout
    assert len(out.strip().splitlines()) == 1


def test_dirs_source(tmp_path):
    d = tmp_path / "snapshots" / "day01"
    d.mkdir(parents=True)
    (d / "server.py").write_text(SERVER, encoding="utf-8")
    r = replay_day(PROFILE, DaySource("dirs", tmp_path / "snapshots", "day{nn}"), 1, install=False)
    assert r.ok, r.steps


def test_failing_install_fails(tagged_repo):
    bad = PROFILE.model_copy(
        update={
            "install": [sys.executable, "-c", "import sys; sys.exit('poetry: lock file mismatch')"]
        }
    )
    r = replay_day(bad, DaySource("git", tagged_repo, "day-{nn}-end"), 1)
    assert not r.ok and "lock file mismatch" in r.steps[-1]


def test_parse_days():
    assert parse_days("1-3,5,3", 30) == [1, 2, 3, 5]
    with pytest.raises(ValueError, match="範囲"):
        parse_days("0-2", 30)


def _has_playwright() -> bool:
    try:
        return (
            subprocess.run(
                ["node", "-e", "require('playwright')"], capture_output=True, check=False
            ).returncode
            == 0
        )
    except FileNotFoundError:
        return False


needs_playwright = pytest.mark.skipif(not _has_playwright(), reason="Node の Playwright が無い")


@needs_playwright
def test_screenshots_are_taken_in_light_scheme(tagged_repo, tmp_path):
    shots = [
        {"name": "top", "path": "/", "login": False},
        {"name": "gone", "path": "/nope", "login": False},
    ]
    r = replay_day(
        PROFILE,
        DaySource("git", tagged_repo, "day-{nn}-end"),
        1,
        shots=shots,
        shots_dir=tmp_path / "shots",
    )
    png = tmp_path / "shots" / "day01" / "top.png"
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    # 404 の画面は撮れても不合格にする（教材に壊れた画面を載せない）
    assert not r.ok and "撮影 gone が失敗（404）" in r.steps[-1]
    assert "✅ 撮影 top（200）" in r.steps


@needs_playwright
def test_login_shot_without_login_config_fails(tagged_repo, tmp_path):
    shots = [{"name": "private", "path": "/tasks", "login": True}]
    r = replay_day(
        PROFILE,
        DaySource("git", tagged_repo, "day-{nn}-end"),
        1,
        shots=shots,
        shots_dir=tmp_path / "s",
    )
    assert not r.ok and "replay.login が無い" in r.steps[-1]


LOGIN_SERVER = """
import http.server, sys, urllib.parse

class H(http.server.BaseHTTPRequestHandler):
    def _go(self, where, cookie=None):
        self.send_response(302)
        self.send_header("Location", where)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def _page(self, body):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        if self.path == "/login":
            return self._page('<h1>LOGIN PAGE</h1><form method="post" action="/login">'
                '<input name="pw" type="password"><button id="go">go</button></form>')
        if self.path == "/tasks":
            if "ok=1" in (self.headers.get("Cookie") or ""):
                return self._page("<h1>TASKS</h1>")
            return self._go("/login")
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        pw = urllib.parse.parse_qs(self.rfile.read(n).decode()).get("pw", [""])[0]
        if pw == "right":
            return self._go("/tasks", "ok=1; Path=/")
        return self._go("/login")

    def log_message(self, *a):
        pass

http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
"""


def _login_shot(tmp_path: Path, password: str) -> dict:
    import socket
    import time

    from educreator.replay import take_shots

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = subprocess.Popen([sys.executable, "-c", LOGIN_SERVER, str(port)])
    try:
        time.sleep(0.5)
        login = {"path": "/login", "fields": {"input[name=pw]": password}, "submit": "#go"}
        shots = [{"name": "tasks", "path": "/tasks", "login": True}]
        return take_shots(f"http://127.0.0.1:{port}", shots, login, tmp_path / "out")[0]
    finally:
        server.kill()
        server.wait()


@needs_playwright
def test_wrong_password_does_not_pass_as_a_logged_in_shot(tmp_path):
    """ログインに失敗してログイン画面（200）が撮れても、撮影は不合格にする。"""
    r = _login_shot(tmp_path, "WRONG")
    assert r["ok"] is False
    assert "ログインが完了しなかった" in r["error"] or "/login" in r["error"]


@needs_playwright
def test_right_password_passes_as_a_logged_in_shot(tmp_path):
    r = _login_shot(tmp_path, "right")
    assert r["ok"] is True and r["status"] == 200
