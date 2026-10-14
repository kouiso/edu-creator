#!/usr/bin/env python3
"""スクリーンショット撮影用CLI。"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from config_models import validate_config  # noqa: E402
from screenshot_manager import (PlaywrightUnavailableError,  # noqa: E402
                                ScreenshotCapture, ScreenshotValidator)


def print_plan(config) -> None:
    """撮影計画を表示する。"""
    print("📸 Screenshot Capture Plan:")
    print(f"   App command: {config.app_startup.command}")
    print(f"   Port: {config.app_startup.port}")
    print(f"   Output: {config.output_dir}")
    print(f"   Total captures: {len(config.captures)}")
    for spec in config.captures:
        print(f"   - {spec.id}: {spec.label} ({spec.url})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture screenshots for task-app tutorials")
    parser.add_argument("--config", required=True, help="Path to edu-config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Plan only, do not capture")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"❌ Config not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f) or {}

    success, config_model, error = validate_config(config_dict)
    if not success or config_model is None:
        print(error)
        sys.exit(1)

    screenshot_config = config_model.screenshots
    if not screenshot_config.enabled:
        print("⚠️  Screenshot capture is disabled in config")
        sys.exit(0)

    if not screenshot_config.captures:
        print("⚠️  No captures defined. Add entries under screenshots.captures.")
        sys.exit(0)

    repo_root = config_path.parent
    output_dir = (repo_root / screenshot_config.output_dir).resolve()

    if args.dry_run:
        print_plan(screenshot_config)
        sys.exit(0)

    capturer = ScreenshotCapture(screenshot_config, repo_root)

    try:
        results = asyncio.run(capturer.capture_all(output_dir))
    except RuntimeError:
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(capturer.capture_all(output_dir))
    except PlaywrightUnavailableError as exc:
        print(str(exc))
        sys.exit(1)

    validator = ScreenshotValidator(output_dir, screenshot_config.metadata_file)
    validation = validator.validate()

    print("\n" + "=" * 60)
    print(f"✅ Captured {len(results)} screenshots")
    print(f"📁 Output directory: {output_dir}")
    if not validation.get("passed", False):
        missing = validation.get("missing", [])
        print(f"⚠️  Missing files: {', '.join(missing)}")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
