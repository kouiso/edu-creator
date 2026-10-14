from typing import Any


def estimate_cost(num_chapters: int, config: dict[str, Any]) -> dict[str, Any]:
    """Estimate API costs before execution."""
    gpt_tokens_per_chapter = 4000
    gemini_tokens_per_chapter = 50000
    gpt_cost_per_1k = 0.03

    total_gpt_tokens = gpt_tokens_per_chapter * num_chapters
    total_gemini_tokens = gemini_tokens_per_chapter * num_chapters
    estimated_cost = (total_gpt_tokens / 1000) * gpt_cost_per_1k

    return {
        "num_chapters": num_chapters,
        "gpt_tokens": total_gpt_tokens,
        "gemini_tokens": total_gemini_tokens,
        "estimated_cost_usd": round(estimated_cost, 2),
        "gemini_within_free_tier": total_gemini_tokens < 1_000_000,
    }
