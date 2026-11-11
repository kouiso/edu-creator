"""LLM-as-Judge（A6・R-6・G4）。Day を5つの次元で採点し、結果を残して管理図で見る。

- 次元: clarity（明確さ）・accessibility（初心者が入れるか）・engagement（意欲）・actionability（手を動かせるか）・
  self_containment（教材だけで完結するか）。各 1〜5 と、その点の根拠（本文の引用）
- 2系統: Judge A は Claude、Judge B は ChatGPT（Codex）。同じ系統どうしの馴れ合い（F1）を避けるため
- 結果は reports/judge/dayNN-<judge>.json に残し、X̄ 管理図（±3σ）で外れた Day を出す。外れた Day は、その Day ではなく
  工程（プロンプト・skill）の問題として調べる（§3.6）
- 較正（E-6）が済んでいない次元は合否に使わない。較正済みの次元は course-spec の judge.calibrated に書く
- 執筆役にはこのルーブリックを見せない（グッドハートの法則。F10）。ルーブリックは judge の中だけに置く
"""

from __future__ import annotations

import json
import statistics
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from educreator.accounts import Account
from educreator.runtime import AgentRequest, for_provider, run

DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("clarity", "明確さ: 説明と手順が一通りにしか読めないか。指示語や省略で読み手が迷わないか"),
    (
        "accessibility",
        "初心者が入れるか: プログラミング未経験の読み手が、前の Day までの知識だけで読めるか。用語は初出で説明しているか",
    ),
    ("engagement", "意欲: 今日作るものと、それが完成品のどこになるかが見え、続けたくなるか"),
    ("actionability", "手を動かせるか: 各 Step で何をどこに書き、何が出れば正しいかが分かるか"),
    (
        "self_containment",
        "教材だけで完結するか: 外部のページや『ソースを参照』に頼らず、この Day だけで進めるか",
    ),
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "object",
            "properties": {
                k: {
                    "type": "object",
                    "properties": {
                        "score": {"type": "integer", "minimum": 1, "maximum": 5},
                        "evidence": {"type": "string"},
                    },
                    "required": ["score", "evidence"],
                }
                for k, _ in DIMENSIONS
            },
            "required": [k for k, _ in DIMENSIONS],
        },
        "worst_step": {"type": "string"},
    },
    "required": ["scores", "worst_step"],
}

RUBRIC = "\n".join(f"- {k}: {d}" for k, d in DIMENSIONS)

PROMPT = """あなたはプログラミング教材の採点者です。次のファイルは、プログラミング未経験の学習者が1日2時間で写経する教材の1日分です。

ファイル: {path}

このファイルを読み、次の5つの次元をそれぞれ 1〜5 で採点してください。5 は直す所が無い、3 は学習者が一度は止まる所がある、
1 は学習者がその日を終えられない、です。点の根拠には本文の短い引用（どの Step のどの文か）を必ず付けてください。
最後に、学習者が最も止まりやすい Step を1つ挙げてください。

{rubric}

ファイルの外は読まないでください。前の Day の内容は、本文が前提として書いている範囲で判断してください。"""


@dataclass(frozen=True)
class JudgeResult:
    day: int
    judge: str
    scores: dict[str, int]
    evidence: dict[str, str]
    worst_step: str
    account: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "judge": self.judge,
            "scores": self.scores,
            "evidence": self.evidence,
            "worst_step": self.worst_step,
            "account": self.account,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }


class JudgeError(Exception):
    pass


def parse(day: int, judge: str, account: str, structured: Any) -> JudgeResult:
    if not isinstance(structured, dict) or "scores" not in structured:
        raise JudgeError(f"Day{day:02d} の採点の形が違う: {str(structured)[:200]}")
    if not isinstance(structured["scores"], dict):
        raise JudgeError(
            f"Day{day:02d} の scores が dict でない: {str(structured['scores'])[:200]}"
        )
    scores, evidence = {}, {}
    for k, _ in DIMENSIONS:
        item = structured["scores"].get(k)
        if (
            not isinstance(item, dict)
            # bool は int の仲間なので、true が 1 点として通らないよう先に外す
            or isinstance(item.get("score"), bool)
            or not isinstance(item.get("score"), int)
            or not 1 <= item["score"] <= 5
        ):
            raise JudgeError(f"Day{day:02d} の {k} の点が 1〜5 の整数でない: {item}")
        scores[k] = item["score"]
        evidence[k] = str(item.get("evidence", ""))
    return JudgeResult(day, judge, scores, evidence, str(structured.get("worst_step", "")), account)


def judge_day(
    md: Path, day: int, account: Account, state_dir: Path | None = None, timeout: float = 900
) -> JudgeResult:
    judge = "A" if account.provider == "claude" else "B"
    req = AgentRequest(
        prompt=PROMPT.format(path=md.name, rubric=RUBRIC),
        cwd=md.parent,
        output_schema=SCHEMA,
        allowed_tools=("Read",),
        permission_mode="plan" if account.provider == "chatgpt" else "default",
        max_turns=6,
    )
    try:
        res = run(
            for_provider(account.provider), account, req, timeout=timeout, state_dir=state_dir
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        # 1 Day の失敗（時間切れ・CLI が無い）で、残りの Day の採点を止めない
        raise JudgeError(
            f"Day{day:02d} の採点が動かなかった（{account.provider}/{account.name}）: {type(e).__name__}: {e}"
        ) from e
    if not res.ok:
        raise JudgeError(
            f"Day{day:02d} の採点が失敗した（{account.provider}/{account.name}）: {res.stderr[-300:] or res.text[-300:]}"
        )
    return parse(day, judge, account.name, res.structured)


def save(result: JudgeResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"day{result.day:02d}-{result.judge}.json"
    p.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return p


def load_all(out_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out_dir.glob("day*-*.json"))]


@dataclass(frozen=True)
class ControlChart:
    dimension: str
    mean: float
    sigma: float
    out_of_control: list[tuple[int, float]]


def control_chart(reports: list[dict[str, Any]], dimension: str) -> ControlChart:
    """Day ごとに2系統の平均（X̄）をとり、全 Day の平均 ±3σ を外れた Day を返す。"""
    per_day: dict[int, list[int]] = {}
    for r in reports:
        per_day.setdefault(int(r["day"]), []).append(int(r["scores"][dimension]))
    xbar = {d: statistics.fmean(v) for d, v in per_day.items()}
    if len(xbar) < 2:
        m = next(iter(xbar.values()), 0.0)
        return ControlChart(dimension, m, 0.0, [])
    m = statistics.fmean(xbar.values())
    s = statistics.stdev(xbar.values())
    out = [(d, v) for d, v in sorted(xbar.items()) if s > 0 and abs(v - m) > 3 * s]
    return ControlChart(dimension, m, s, out)


def gate(
    reports: list[dict[str, Any]],
    calibrated: list[str],
    mean_min: float = 4.5,
    each_min: float = 4.0,
) -> list[str]:
    """較正済みの次元だけで R-6 を判定する（2系統の平均 ≥ 4.5、各 Day の各次元 ≥ 4.0）。問題を返す。"""
    known = {k for k, _ in DIMENSIONS}
    unknown = [d for d in calibrated if d not in known]
    if unknown:
        # 綴りの違いで KeyError の traceback になったり、較正したつもりの次元が黙って合否から外れたりしない
        raise ValueError(
            f"judge.calibrated に知らない次元がある: {unknown}（使える: {sorted(known)}）"
        )
    problems: list[str] = []
    for dim in calibrated:
        vals = [int(r["scores"][dim]) for r in reports]
        if not vals:
            continue
        if statistics.fmean(vals) < mean_min:
            problems.append(f"{dim} の平均 {statistics.fmean(vals):.2f} < {mean_min}")
        per_day: dict[int, list[int]] = {}
        for r in reports:
            per_day.setdefault(int(r["day"]), []).append(int(r["scores"][dim]))
        for d, v in sorted(per_day.items()):
            if statistics.fmean(v) < each_min:
                problems.append(f"Day{d:02d} の {dim} {statistics.fmean(v):.2f} < {each_min}")
    return problems
