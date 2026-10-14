"""スクリーンショット撮影・検証ユーティリティ。"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from config.models import ScreenshotCaptureSpec, ScreenshotConfig

try:  # Playwrightが未インストールの場合はスキップできるようにする
    from playwright.async_api import async_playwright
except ImportError:  # pragma: no cover - 環境依存
    async_playwright = None


class PlaywrightUnavailableError(RuntimeError):
    """Playwrightがインストールされていない場合に発生させるエラー。"""


@dataclass
class ScreenshotMetadata:
    """スクリーンショットのメタデータ。"""

    id: str
    label: str
    filename: str
    url: str
    viewport: dict[str, int]
    captured_at: str
    app_version: str
    notes: str = ""


class ScreenshotCapture:
    """Playwrightを用いたスクリーンショット撮影クラス。"""

    def __init__(self, config: ScreenshotConfig, repo_root: Path | None = None):
        self.config = config
        self.repo_root = repo_root or Path.cwd()
        self.app_process: asyncio.subprocess.Process | None = None
        self.metadata_list: list[ScreenshotMetadata] = []

    async def _wait_for_ready(self) -> bool:
        """ポートのオープンまたはログのキーワードを待機する。"""
        deadline = asyncio.get_event_loop().time() + self.config.app_startup.wait_time_seconds
        ready_pattern = self.config.app_startup.ready_pattern
        stdout = self.app_process.stdout if self.app_process else None

        while asyncio.get_event_loop().time() < deadline:
            if ready_pattern and stdout:
                try:
                    line = await asyncio.wait_for(stdout.readline(), timeout=0.2)
                    if line and ready_pattern in line.decode(errors="ignore"):
                        return True
                except asyncio.TimeoutError:
                    pass

            if await self._is_port_open():
                return True

            if self.app_process and self.app_process.returncode is not None:
                return False

            await asyncio.sleep(0.5)

        return await self._is_port_open()

    async def _is_port_open(self) -> bool:
        """アプリのポートが開いているか確認する。"""
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", self.config.app_startup.port)
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:  # noqa: BLE001
            return False

    async def start_app(self) -> bool:
        """アプリを起動し、待機パターンを確認する。"""
        if self.app_process:
            return True

        if not self.config.app_startup.command:
            return True

        self.app_process = await asyncio.create_subprocess_shell(
            self.config.app_startup.command,
            cwd=str(self.repo_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        return await self._wait_for_ready()

    async def stop_app(self) -> None:
        """起動したアプリを停止する。"""
        if not self.app_process:
            return

        self.app_process.terminate()
        try:
            await asyncio.wait_for(self.app_process.wait(), timeout=5)
        except asyncio.TimeoutError:  # pragma: no cover - 稀なケース
            self.app_process.kill()
            await self.app_process.wait()

    async def capture(self, spec: ScreenshotCaptureSpec, output_dir: Path) -> Path | None:
        """単一スクリーンショットを撮影する。"""
        if async_playwright is None:
            raise PlaywrightUnavailableError(
                "Playwright is not installed. Run `pip install -e .[screenshot]` and `playwright install chromium`."
            )

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.config.headless,
                    slow_mo=self.config.slow_motion_ms or 0,
                )
                context = await browser.new_context(
                    viewport={
                        "width": spec.viewport_width,
                        "height": spec.viewport_height,
                    }
                )
                page = await context.new_page()

                await page.goto(f"http://localhost:{self.config.app_startup.port}{spec.url}")

                if spec.setup_script:
                    await page.evaluate(spec.setup_script)

                if spec.wait_for_selector:
                    await page.wait_for_selector(spec.wait_for_selector, timeout=5000)

                filename = self.config.filename_pattern.format(
                    id=spec.id,
                    label=spec.label,
                    chapter_id=spec.id.split("_")[0],
                    step_id=spec.id,
                )
                output_path = output_dir / filename

                await page.screenshot(path=str(output_path), full_page=spec.full_page)

                metadata = ScreenshotMetadata(
                    id=spec.id,
                    label=spec.label,
                    filename=filename,
                    url=spec.url,
                    viewport={"width": spec.viewport_width, "height": spec.viewport_height},
                    captured_at=datetime.now().isoformat(),
                    app_version="task-app",
                )
                self.metadata_list.append(metadata)

                await browser.close()
                return output_path
        except PlaywrightUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Screenshot capture failed for {spec.id}: {exc}")
            return None

    async def capture_all(self, output_dir: Path) -> dict[str, str]:
        """設定されたすべてのスクリーンショットを撮影する。"""
        output_dir.mkdir(parents=True, exist_ok=True)

        if not self.config.captures:
            print("⚠️  No captures defined. Skipping screenshot phase.")
            return {}

        if not await self.start_app():
            print("❌ アプリの起動に失敗しました")
            await self.stop_app()
            return {}

        results: dict[str, str] = {}
        try:
            for spec in self.config.captures:
                print(f"📸 Capturing: {spec.label}")
                result = await self.capture(spec, output_dir)
                if result:
                    results[spec.id] = str(result)
                    print(f"   ✅ Saved to {result.name}")
                else:
                    print("   ❌ Failed")
        finally:
            await self.stop_app()
            self._save_metadata(output_dir)

        return results

    def _save_metadata(self, output_dir: Path) -> None:
        """撮影メタデータをJSONで保存する。"""
        metadata_file = output_dir / self.config.metadata_file
        data = [
            {
                "id": m.id,
                "label": m.label,
                "filename": m.filename,
                "url": m.url,
                "viewport": m.viewport,
                "captured_at": m.captured_at,
                "app_version": m.app_version,
            }
            for m in self.metadata_list
        ]
        metadata_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class ScreenshotValidator:
    """スクリーンショットファイルとメタデータの検証。"""

    def __init__(self, output_dir: Path, metadata_file: str = "metadata.json"):
        self.output_dir = output_dir
        self.metadata_path = output_dir / metadata_file

    def validate(self) -> dict[str, Any]:
        """メタデータと実ファイルの整合性を確認する。"""
        if not self.metadata_path.exists():
            return {"passed": False, "missing": [], "error": "metadata.json not found"}

        try:
            metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            return {"passed": False, "missing": [], "error": str(exc)}

        missing: list[str] = []
        for item in metadata:
            filepath = self.output_dir / item.get("filename", "")
            if not filepath.exists():
                missing.append(item.get("filename", ""))

        return {
            "passed": len(missing) == 0,
            "missing": missing,
            "total": len(metadata),
            "metadata": metadata,
        }


class ScreenshotPlaceholderHandler:
    """マークダウン内のスクリーンショットプレースホルダーを処理する。"""

    PLACEHOLDER_PATTERNS = [
        r'【スクリーンショット:\s*([^】]+)】',
        r'\[スクリーンショット:\s*([^\]]+)\]',
        r'【スクリーンショット\s*([^】]*)】',
    ]

    def __init__(self, markdown_path: Path, screenshots_dir: Path):
        self.markdown_path = markdown_path
        self.screenshots_dir = screenshots_dir
        self.content = markdown_path.read_text(encoding='utf-8')

    def find_placeholders(self) -> list[dict[str, Any]]:
        """マークダウン内の全プレースホルダーを検出する。"""
        placeholders = []
        for pattern in self.PLACEHOLDER_PATTERNS:
            for match in re.finditer(pattern, self.content):
                placeholders.append({
                    'full_match': match.group(0),
                    'description': match.group(1) if match.lastindex else '',
                    'position': match.start(),
                })
        return placeholders

    def replace_with_images(self, image_mapping: dict[str, str]) -> str:
        """プレースホルダーを実際の画像パスに置換する。

        Args:
            image_mapping: プレースホルダー説明 → 画像パスの辞書

        Returns:
            置換後のマークダウンコンテンツ
        """
        result = self.content
        for description, image_path in image_mapping.items():
            markdown_image = f'![{description}]({image_path})'
            # 複数のパターンに対応
            result = result.replace(
                f'【スクリーンショット: {description}】', markdown_image
            )
            result = result.replace(
                f'【スクリーンショット:{description}】', markdown_image
            )
            result = result.replace(
                f'[スクリーンショット: {description}]', markdown_image
            )
        return result

    def replace_with_text(self) -> str:
        """プレースホルダーを説明テキストに置換する。

        Returns:
            置換後のマークダウンコンテンツ
        """
        result = self.content
        for pattern in self.PLACEHOLDER_PATTERNS:
            result = re.sub(
                pattern,
                r'> **画面確認**: \1の画面が表示されていることを確認してください。',
                result
            )
        return result

    def get_report(self) -> str:
        """プレースホルダーのレポートを生成する。"""
        placeholders = self.find_placeholders()
        if not placeholders:
            return "スクリーンショットプレースホルダーは見つかりませんでした。"

        report = [f"スクリーンショットプレースホルダー: {len(placeholders)}個"]
        for i, p in enumerate(placeholders, 1):
            report.append(f"  {i}. {p['description'][:50]}...")
        return "\n".join(report)
