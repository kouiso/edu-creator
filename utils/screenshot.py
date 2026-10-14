import asyncio
from pathlib import Path
from typing import Any

from config.models import ScreenshotConfig
from screenshot_manager import (PlaywrightUnavailableError, ScreenshotCapture,
                                ScreenshotValidator)


def capture_screenshots_if_enabled(config: dict[str, Any], repo_root: Path) -> dict[str, str]:
    """スクリーンショット設定が有効な場合に撮影を実行する。"""
    screenshots_cfg = config.get("screenshots")
    if not screenshots_cfg or not screenshots_cfg.get("enabled"):
        return {}

    try:
        screenshot_config = ScreenshotConfig.model_validate(screenshots_cfg)
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️  Screenshot config is invalid: {exc}")
        return {}

    output_dir = (repo_root / screenshot_config.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("📸 Screenshot capture is enabled. Starting app and browser...")
    print("=" * 60)

    capturer = ScreenshotCapture(screenshot_config, repo_root)

    try:
        results = asyncio.run(capturer.capture_all(output_dir))
    except RuntimeError:
        # 既存のイベントループがある場合のフォールバック
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(capturer.capture_all(output_dir))
    except PlaywrightUnavailableError as exc:
        print(str(exc))
        return {}

    validator = ScreenshotValidator(output_dir, screenshot_config.metadata_file)
    validation = validator.validate()

    print(f"📁 Screenshot output: {output_dir}")
    print(f"✅ Captured: {len(results)} files")
    if not validation.get("passed", False):
        missing = validation.get("missing", [])
        print(f"⚠️  Missing files detected: {', '.join(missing)}")

    return results
