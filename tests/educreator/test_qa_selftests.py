"""取り込んだ検査（educreator/checks/qa）の退行テストを、取り込み元と同じ値（flask の qa）で1本ずつ動かす。

退行テストは取り込み元の形（`python3 selftest_x.py` で動き、0 以外で終わると失敗）のまま持つ。
ここでは pytest の1件として数えるだけにする。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from educreator.checks import qa_config

QA_TESTS = sorted((Path(__file__).parent / "qa").glob("selftest_*.py"))


@pytest.mark.parametrize("path", QA_TESTS, ids=[p.stem for p in QA_TESTS])
def test_vendored_selftest(path, tmp_path):
    env = dict(os.environ)
    env["EDU_CREATOR_QA_JSON"] = json.dumps(
        qa_config("flask", {"gui_services": ["Render"]}, tmp_path)
    )
    proc = subprocess.run(
        [sys.executable, str(path)],
        env=env,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]


def test_checks_refuse_to_run_without_config(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "EDU_CREATOR_QA_JSON"}
    script = (
        Path(__file__).resolve().parents[2] / "educreator" / "checks" / "qa" / "check_no_skip.py"
    )
    proc = subprocess.run(
        [sys.executable, str(script), str(tmp_path)], env=env, capture_output=True, text=True
    )
    assert proc.returncode != 0
    assert "EDU_CREATOR_QA_JSON が無い" in proc.stderr
