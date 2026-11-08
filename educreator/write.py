"""Step を1つ書く（A5 の最小の形）。恒久ルール「実コードを1か所変える → 動かして確かめる → その差分と理由を書く」を、
道具を使えるエージェント1回の実行で行う。

エージェントには次を渡す:
- 正解のコード（目標）: 写す先の形としてだけ使い、教材の元にはしない
- 作業ツリー: 学習者のツリーと同じ、前の Step までのコード。ここだけを変える
- 書き先: 教材の Day のファイル。Step を1つ末尾に足す
- 前の Day までに説明した用語（chapter_context）

書き方の決まり（Step の4つの要素、コードブロックの1行目の書き込み先）は profile と course-spec から作る。
Judge のルーブリックは渡さない（F10）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from educreator import cassette
from educreator.accounts import Account
from educreator.profiles import StackProfile
from educreator.runtime import AgentRequest, RunResult, for_provider, run

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "changed_files": {"type": "array", "items": {"type": "string"}},
        "verified_with": {"type": "string"},
        "step_title": {"type": "string"},
    },
    "required": ["changed_files", "verified_with", "step_title"],
}

PROMPT = """あなたはプログラミング未経験の人向けの写経教材を書いています。今から Step を1つだけ書きます。

- 作業ツリー: このフォルダ（学習者の手元と同じ、前の Step までのコード）
- 書き先: {material}（Day {day:02d} の本文。末尾に Step を1つ足す）
- 今回の Step でやること: {goal}
{context}
次の順で進めてください。順番を入れ替えないでください。
1. 作業ツリーの実際のコードを、今回の Step の分だけ1か所変える（ファイルは {max_files} つまで）
2. 動かして確かめる（確かめ方: {verify}）。確かめた出力を覚えておく
3. 書き先の末尾に Step を1つ足す。見出しは `### Step N: <やること>（<分>分）`。次の4つを必ず書く:
   - 今やることを1文、なぜ必要かを1〜2文
   - コード。1で変えた実際のファイルから写す（手で打ち直さない）。1行目に書き込み先を {marker} の形で書く
   - 確認方法: 実行するコマンドと、2で実際に出た出力
   - よくあるエラー: エラーメッセージ・原因・直し方の表
4. コードブロックは {block_lines} 行まで。超えるなら Step を分ける代わりに、変える量を減らす

最後に、変えたファイル・確かめたコマンド・Step の見出しを返してください。"""


@dataclass(frozen=True)
class StepTask:
    day: int
    goal: str
    verify: str
    material: Path
    context: str = ""


def request_for(
    task: StepTask, tree: Path, profile: StackProfile, block_lines: int, max_files: int
) -> AgentRequest:
    ext = next(iter(profile.filepath_comment))
    marker = profile.filepath_comment[ext].replace("{path}", "<ファイルのパス>")
    context = f"- 前の Day までに説明した用語: {task.context}\n" if task.context else ""
    return AgentRequest(
        prompt=PROMPT.format(
            material=task.material.relative_to(tree).as_posix()
            if task.material.is_relative_to(tree)
            else task.material,
            day=task.day,
            goal=task.goal,
            context=context,
            max_files=max_files,
            verify=task.verify,
            marker=marker,
            block_lines=block_lines,
        ),
        cwd=tree,
        output_schema=SCHEMA,
        allowed_tools=("Read", "Edit", "Write", "Glob", "Grep", "Bash"),
        permission_mode="acceptEdits",
        max_turns=40,
    )


def _request_key(req: AgentRequest) -> dict[str, Any]:
    # 録画と照合する依頼の中身。作業ツリーの場所（機械ごとに違う）は含めない
    return {"prompt": req.prompt, "schema": req.output_schema, "tools": list(req.allowed_tools)}


def write_step(
    req: AgentRequest,
    account: Account | None,
    cassette_path: Path | None = None,
    record: bool = False,
    state_dir: Path | None = None,
) -> RunResult:
    """Step を1つ書く。cassette_path があれば、record なら録画し、そうでなければ再生する（LLM を呼ばない）。"""
    key = _request_key(req)
    if cassette_path is not None and not record:
        return cassette.play(cassette_path, req.cwd, key)
    if account is None:
        raise ValueError("録画の再生でないなら、実行するアカウントが要る")
    before = cassette.snapshot(req.cwd)
    res = run(for_provider(account.provider), account, req, timeout=1800, state_dir=state_dir)
    if cassette_path is not None:
        cassette.save(cassette_path, key, res, cassette.changes(req.cwd, before), req.cwd)
    return res
