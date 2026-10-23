from main import DEFAULT_CONFIG, estimate_cost, load_config


def test_load_config_deep_merges_without_mutating_defaults(tmp_path):
    config_file = tmp_path / "edu-config.yaml"
    config_file.write_text(
        """
safety:
  max_rpm: 5
""",
        encoding="utf-8",
    )

    config = load_config(str(config_file))

    # 指定した値だけが上書きされ、同じ階層の他の既定値は残る
    assert config["safety"]["max_iterations"] == 3
    assert config["safety"]["max_rpm"] == 5
    # 既定値の辞書そのものは書き換わらない（浅いコピーだと 10 -> 5 に変わる）
    assert DEFAULT_CONFIG["safety"]["max_rpm"] == 10


def test_estimate_cost_scales_by_chapter_count():
    estimate = estimate_cost(3, DEFAULT_CONFIG)

    assert estimate["num_chapters"] == 3
    assert estimate["gpt_tokens"] == 24000
    assert estimate["gemini_tokens"] == 180000
    assert estimate["estimated_cost_usd"] == 0.72
    assert estimate["gemini_within_free_tier"] is True
