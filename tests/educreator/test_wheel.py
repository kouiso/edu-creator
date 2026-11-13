"""wheel にコードが入り、2つの入口が editable 以外でも起動することを確かめる。

pyproject の only-include をグロブで書いたとき、wheel には dist-info しか入らず、
edu-creator も edu-creator-legacy も ModuleNotFoundError で落ちていた。editable では
dev-mode-dirs のおかげで動くため、通常の試験では気づけない。
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# wheel の展開先だけを import の起点にして、リポジトリ直下（editable の .pth）を外した状態で import する
IMPORT_SCRIPT = """
import sys
root = sys.argv[1]
sys.path = [sys.argv[2]] + [p for p in sys.path if p not in ("", root)]
import importlib
for name in sys.argv[3:]:
    importlib.import_module(name)
"""


@pytest.fixture(scope="module")
def wheel_dir(tmp_path_factory):
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv が無いので wheel を作れない")
    out = tmp_path_factory.mktemp("wheel")
    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(out.glob("*.whl"))
    unpacked = out / "unpacked"
    with zipfile.ZipFile(wheel) as z:
        z.extractall(unpacked)
    return unpacked


def test_wheel_contains_both_entry_points(wheel_dir):
    files = {p.relative_to(wheel_dir).as_posix() for p in wheel_dir.rglob("*") if p.is_file()}
    assert "educreator/cli.py" in files
    assert "main.py" in files
    assert "config_models.py" in files
    assert any(f.startswith("educreator/profiles/") and f.endswith(".yaml") for f in files)


def test_wheel_contains_agent_skill_files(wheel_dir):
    files = {p.relative_to(wheel_dir).as_posix() for p in wheel_dir.rglob("*") if p.is_file()}
    assert "educreator/agent-skill/material-writing/SKILL.md" in files
    assert "educreator/agent-skill/material-writing/hook/material_writing_gate.py" in files
    assert "educreator/agent-skill/material-writing/reference/voice-spec.md" in files


def test_wheel_imports_without_repo_checkout(wheel_dir, tmp_path):
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            IMPORT_SCRIPT,
            str(ROOT),
            str(wheel_dir),
            "educreator.cli",
            "main",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
