"""Judge（A6）の、LLM を呼ばない部分のテスト。"""

import pytest

from educreator.judge import DIMENSIONS, JudgeError, control_chart, gate, parse

DIMS = [k for k, _ in DIMENSIONS]


def _structured(score: int = 4, **over: int) -> dict:
    return {
        "scores": {k: {"score": over.get(k, score), "evidence": f"{k} の根拠"} for k in DIMS},
        "worst_step": "Step 3",
    }


def _report(day: int, judge: str = "A", score: int = 5, **over: int) -> dict:
    return {"day": day, "judge": judge, "scores": {k: over.get(k, score) for k in DIMS}}


def test_parse_keeps_scores_and_evidence():
    r = parse(6, "A", "personal-1", _structured(4, clarity=3))
    assert r.scores["clarity"] == 3 and r.scores["engagement"] == 4
    assert r.evidence["clarity"] == "clarity の根拠" and r.worst_step == "Step 3"


@pytest.mark.parametrize("bad", [None, {"x": 1}, _structured(6), _structured(0)])
def test_parse_rejects_out_of_range_or_wrong_shape(bad):
    with pytest.raises(JudgeError):
        parse(1, "A", "p", bad)


def test_control_chart_flags_outlier_day():
    reports = [_report(d, score=5) for d in range(1, 20)] + [_report(20, score=1)]
    c = control_chart(reports, "clarity")
    assert [d for d, _ in c.out_of_control] == [20]


def test_control_chart_averages_both_judges_per_day():
    reports = [_report(1, "A", 4), _report(1, "B", 2), _report(2, "A", 3), _report(2, "B", 3)]
    c = control_chart(reports, "clarity")
    assert c.mean == pytest.approx(3.0)


def test_gate_uses_only_calibrated_dimensions():
    reports = [_report(1, score=5, engagement=2), _report(2, score=5)]
    # 較正していない次元は、低くても合否に使わない（E-6）
    assert gate(reports, calibrated=["clarity"]) == []
    problems = gate(reports, calibrated=["engagement"])
    assert "Day01 の engagement 2.00 < 4.0" in problems
    assert any(p.startswith("engagement の平均") for p in problems)
