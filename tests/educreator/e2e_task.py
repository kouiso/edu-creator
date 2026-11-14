"""E2E（E-8）で録画と再生が同じ依頼を作るための、サンプルアプリの Step の定義。"""

from pathlib import Path

from educreator.profiles import load_profile
from educreator.runtime import AgentRequest
from educreator.write import StepTask, request_for

FIXTURE = Path(__file__).parent / "fixtures" / "sample-app"
CASSETTE = Path(__file__).parent / "fixtures" / "cassettes" / "sample-day01-step2.json"
VERIFY = "python3 -c \"from app.todo import add, list_items; add('買い物'); add('洗濯'); print(list_items())\""


def make_task(tree: Path) -> StepTask:
    return StepTask(
        day=1,
        goal="足したやることを、番号付きの1行ずつの文字列で返す関数 list_items を app/todo.py に足す",
        verify=VERIFY,
        material=tree / "material" / "day01_todo.md",
        context="関数・リスト・f 文字列・for（Day01 の Step 1 まで）",
    )


def make_request(tree: Path) -> AgentRequest:
    return request_for(make_task(tree), tree, load_profile("flask"), block_lines=25, max_files=1)
