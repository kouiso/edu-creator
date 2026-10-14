# 📸 スクリーンショット自動撮影機能 - 設計仕様書

## 概要

task-app を自動起動し、Playwright でブラウザ制御してスクリーンショットを撮影。
チュートリアル生成時に自動で埋め込む仕組み。

**核心思想**: AI の判定ではなく、**仕組みで実行・記録・検証**する。

---

## アーキテクチャ

```
┌─────────────────────────────────────────────────────┐
│  edu-creator/                                        │
│  ├─ config_models.py (拡張)                          │
│  │  └─ ScreenshotConfig モデル追加                   │
│  │                                                   │
│  ├─ screenshot_manager.py (新規)                     │
│  │  ├─ ScreenshotCapture: 撮影実行                   │
│  │  ├─ ScreenshotMetadata: メタデータ管理            │
│  │  └─ ScreenshotValidator: ファイル検証             │
│  │                                                   │
│  ├─ script/                                          │
│  │  └─ capture_screenshots.py (新規)                 │
│  │     └─ CLI でスクショ撮影実行                     │
│  │                                                   │
│  ├─ prompt/agent/                                    │
│  │  └─ scribe.py (拡張)                              │
│  │     └─ スクショパスを自動埋め込み                 │
│  │                                                   │
│  ├─ prompt/task/                                     │
│  │  └─ write.py (拡張)                               │
│  │     └─ スクショ埋め込みガイド追加                 │
│  │                                                   │
│  ├─ quality_checker.py (拡張)                        │
│  │  └─ check_screenshot_files()                      │
│  │     スクショファイルの実在確認                    │
│  │                                                   │
│  └─ main.py (拡張)                                   │
│     └─ スクショ撮影フェーズを追加                    │
│                                                      │
├─ edu-config.yaml (拡張)                              │
│  └─ screenshots セクション追加                       │
│     撮影タイミング・ページ定義                       │
│                                                      │
    └─ material/                                           │
        └─ screenshot/                                      │
            ├─ day01_step01_login.png                        │
            ├─ day01_step02_dashboard.png                    │
            └─ metadata.json                                 │
         ファイル、撮影時刻、ページ情報等              │
```

---

## 1. Config Model 拡張

### 新規: ScreenshotConfig

```python
# config_models.py に追加

class ScreenshotCaptureSpec(BaseModel):
    """単一スクリーンショット撮影仕様"""
    id: str  # day01_step01_login
    label: str  # "ログイン画面"

    # ナビゲーション方法
    url: str = "/"  # 例: /login, /dashboard/tasks
    wait_for_selector: str = ""  # 例: [data-testid="login-form"]

    # オプション: JS実行（初期データ設定等）
    setup_script: str = ""  # 例: "window.localStorage.setItem(...)"

    # 撮影設定
    viewport_width: int = 1280
    viewport_height: int = 720
    full_page: bool = False  # ページ全体か、ビューポート分か

class ScreenshotConfig(BaseModel):
    """スクリーンショット撮影設定"""
    enabled: bool = True

    # アプリ起動設定
    app_startup: dict = {
        "command": "npm run dev",
        "port": 3000,
        "wait_time_seconds": 10,
        "ready_pattern": "ready started server"
    }

    # ブラウザ設定
    headless: bool = True
    slow_motion_ms: int = 100  # AIが読みやすいように少しスロー再生

    # 認証・初期状態
    auth: dict = {
        "enabled": False,
        "login_url": "/login",
        "username": "demo@example.com",
        "password": "password",
        "wait_for_redirect": "/dashboard"
    }

    # 撮影仕様一覧
    captures: list[ScreenshotCaptureSpec] = Field(default_factory=list)

    # 出力設定
    output_dir: str = "material/screenshot"
    filename_pattern: str = "{chapter_id}_{step_id}_{label}.png"
    metadata_file: str = "metadata.json"
```

### yaml での設定例

```yaml
screenshots:
  enabled: true

  app_startup:
    command: "npm run dev"
    port: 3000
    wait_time_seconds: 10
    ready_pattern: "ready started server"

  headless: true

  auth:
    enabled: false  # 今は認証なし（後で対応）

  captures:
    # Day 1
    - id: day01_step01
      label: "初期表示"
      url: "/"
      wait_for_selector: "h1"
      viewport_width: 1280
      viewport_height: 720

    - id: day01_step02
      label: "タスク作成ボタン"
      url: "/dashboard/tasks"
      wait_for_selector: "[data-testid='new-task-button']"

    # Day 5（コメント機能）
    - id: day05_step03
      label: "コメント入力欄"
      url: "/dashboard/tasks"
      setup_script: |
        // タスク開く、等の操作
        document.querySelector('[data-testid="task-row-1"]')?.click();
      wait_for_selector: "[data-testid='comment-form']"
```

---

## 2. ScreenshotManager (新規モジュール)

### ファイル: `screenshot_manager.py`

```python
"""
スクリーンショット撮影・メタデータ管理
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import subprocess
import asyncio
from typing import Optional

try:
    from playwright.async_api import async_playwright, Page
except ImportError:
    async_playwright = None
    Page = None

@dataclass
class ScreenshotMetadata:
    """スクリーンショットのメタデータ"""
    id: str
    label: str
    filename: str
    url: str
    viewport: dict  # {"width": 1280, "height": 720}
    captured_at: str  # ISO 8601
    app_version: str
    notes: str = ""

class ScreenshotCapture:
    """Playwright でスクリーンショット撮影"""

    def __init__(self, config: ScreenshotConfig, app_port: int = 3000):
        self.config = config
        self.app_port = app_port
        self.app_process = None
        self.metadata_list: list[ScreenshotMetadata] = []

    async def start_app(self) -> bool:
        """task-app を起動"""
        # npm run dev を起動
        # ログを監視して ready を確認
        # 失敗時は False を返す
        ...

    async def stop_app(self):
        """アプリプロセスを停止"""
        if self.app_process:
            self.app_process.terminate()
            await self.app_process.wait()

    async def capture(self, spec: ScreenshotCaptureSpec, output_dir: Path) -> Optional[Path]:
        """
        単一スクリーンショットを撮影

        Returns:
            撮影したファイルパス、失敗時は None
        """
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.config.headless)
                context = await browser.new_context(
                    viewport={
                        "width": spec.viewport_width,
                        "height": spec.viewport_height
                    }
                )
                page = await context.new_page()

                # セットアップスクリプト実行
                if spec.setup_script:
                    await page.evaluate(spec.setup_script)

                # ページナビゲート
                await page.goto(f"http://localhost:{self.app_port}{spec.url}")

                # セレクタ待機
                if spec.wait_for_selector:
                    await page.wait_for_selector(spec.wait_for_selector, timeout=5000)

                # スクリーンショット撮影
                filename = self.config.filename_pattern.format(
                    chapter_id=spec.id.split("_")[0],
                    step_id=spec.id,
                    label=spec.label
                )
                output_path = output_dir / filename

                await page.screenshot(
                    path=str(output_path),
                    full_page=spec.full_page
                )

                # メタデータ記録
                metadata = ScreenshotMetadata(
                    id=spec.id,
                    label=spec.label,
                    filename=filename,
                    url=spec.url,
                    viewport={"width": spec.viewport_width, "height": spec.viewport_height},
                    captured_at=datetime.now().isoformat(),
                    app_version="task-app v0.1.0"
                )
                self.metadata_list.append(metadata)

                await browser.close()
                return output_path

        except Exception as e:
            print(f"❌ Screenshot capture failed: {spec.id}: {e}")
            return None

    async def capture_all(self, output_dir: Path) -> dict[str, str]:
        """全スクリーンショット撮影"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # アプリ起動
        if not await self.start_app():
            print("❌ Failed to start app")
            return {}

        results = {}
        try:
            for spec in self.config.captures:
                print(f"📸 Capturing: {spec.label}")
                result = await self.capture(spec, output_dir)
                if result:
                    results[spec.id] = str(result)
                    print(f"   ✅ Saved to {result.name}")
                else:
                    print(f"   ❌ Failed")
        finally:
            await self.stop_app()

        # メタデータを JSON で保存
        self._save_metadata(output_dir)

        return results

    def _save_metadata(self, output_dir: Path):
        """メタデータを JSON で保存"""
        metadata_file = output_dir / self.config.metadata_file
        data = [
            {
                "id": m.id,
                "label": m.label,
                "filename": m.filename,
                "url": m.url,
                "viewport": m.viewport,
                "captured_at": m.captured_at,
                "app_version": m.app_version
            }
            for m in self.metadata_list
        ]
        with open(metadata_file, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class ScreenshotValidator:
    """スクリーンショットファイルの検証"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.metadata_file = output_dir / "metadata.json"

    def validate(self) -> dict[str, any]:
        """ファイルの実在確認"""
        if not self.metadata_file.exists():
            return {"passed": False, "error": "metadata.json not found"}

        with open(self.metadata_file) as f:
            metadata = json.load(f)

        missing = []
        for item in metadata:
            filepath = self.output_dir / item["filename"]
            if not filepath.exists():
                missing.append(item["filename"])

        return {
            "passed": len(missing) == 0,
            "total": len(metadata),
            "missing": missing,
            "metadata": metadata
        }
```

---

## 3. CLI スクリプト

### ファイル: `script/capture_screenshots.py`

```bash
#!/usr/bin/env python3
"""
スクリーンショット撮影 CLI

使用法:
    python script/capture_screenshots.py --config ../edu-config.yaml
"""

import argparse
import asyncio
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Capture screenshots for tutorials")
    parser.add_argument("--config", required=True, help="Path to edu-config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be captured")
    args = parser.parse_args()

    # Config 読み込み & 検証
    from config_models import validate_config
    import yaml

    with open(args.config) as f:
        config_dict = yaml.safe_load(f)

    success, config, error = validate_config(config_dict)
    if not success:
        print(f"❌ Config validation failed: {error}")
        sys.exit(1)

    screenshot_config = config.screenshots
    if not screenshot_config.enabled:
        print("⚠️  Screenshot capture is disabled")
        sys.exit(0)

    # Dry-run: 撮影予定の確認
    if args.dry_run:
        print("📸 Screenshot Capture Plan:")
        print(f"   App: {screenshot_config.app_startup['command']}")
        print(f"   Port: {screenshot_config.app_startup['port']}")
        print(f"   Output: {screenshot_config.output_dir}")
        print(f"   Total captures: {len(screenshot_config.captures)}")
        for spec in screenshot_config.captures:
            print(f"   - {spec.id}: {spec.label} ({spec.url})")
        sys.exit(0)

    # 実際の撮影
    from screenshot_manager import ScreenshotCapture

    output_dir = Path(screenshot_config.output_dir)
    capturer = ScreenshotCapture(screenshot_config)

    results = asyncio.run(capturer.capture_all(output_dir))

    print("\n" + "=" * 60)
    print(f"✅ Captured {len(results)} screenshots")
    print(f"📁 Output directory: {output_dir.absolute()}")
    print("=" * 60)
```

---

## 4. Quality Checker 拡張

### `quality_checker.py` に追加

```python
def check_screenshot_files(markdown_content: str, screenshot_dir: Path) -> dict[str, any]:
    """
    マークダウン内のスクショ参照が、実ファイルに存在するか確認

    機械的チェック（AIの判定なし）
    """
    import re

    # マークダウン内のスクショ参照を抽出
    # 形式: ![label](./screenshot/filename.png)
    screenshot_refs = re.findall(
        r'!\[([^\]]+)\]\(\.\/screenshot\/([^)]+\.png)\)',
        markdown_content
    )

    missing = []
    found = []

    for label, filename in screenshot_refs:
        filepath = screenshot_dir / filename
        if filepath.exists():
            found.append(filename)
        else:
            missing.append(filename)

    return {
        "passed": len(missing) == 0,
        "found": found,
        "missing": missing,
        "total": len(screenshot_refs),
        "issues": [
            f"❌ Screenshot not found: {f}" for f in missing
        ]
    }
```

---

## 5. Scribe エージェント拡張

### `prompt/agent/scribe.py` に追加

```python
SCRIBE_BACKSTORY_EXTENDED = """
...existing backstory...

【スクリーンショット埋め込みルール】
マークダウン内にスクショを埋め込む場合は、以下の形式を使用してください：

```markdown
## ステップX: 〇〇画面を開く

以下の画面が表示されます：

![〇〇画面](./screenshot/day01_step02_dashboard.png)

このように...
```

【重要】
- スクショのIDは ./screenshot/FILENAME 形式
- FILENAMEは config.yaml で定義された撮影仕様の ID と一致
- AIが作成したスクショ参照は、必ず実ファイルが存在することを確認
- スクショが存在しない場合は、Validatorが検出して指摘
"""
```

---

## 6. Main.py 統合

### 実行フロー

```python
# run_chapter() 関数内

def run_chapter(...) -> str:
    # Phase 1: Research & Outline
    # Phase 2: Writing
    # Phase 3: Screenshot Capture (新規)
    # Phase 4: Quality Check

    # === Phase 3 NEW: Screenshot Capture ===
    if config.get("screenshots", {}).get("enabled"):
        print(f"\n📸 Phase 3: Capturing screenshots...")

        screenshot_config = config.screenshots

        # スクリーンショット撮影
        capturer = ScreenshotCapture(screenshot_config)
        results = await capturer.capture_all(output_dir / "screenshot")

        # 撮影結果をログに記録
        log_msg = f"✅ Captured {len(results)} screenshots"
        print(log_msg)
        metadata.screenshots = results

    # === Phase 4: Quality Check ===
    # このときにスクショファイルの実在確認も実施
    passed, attempts, validation_log = validate_and_fix_quality(...)
```

---

## 7. 実行フロー

### Step 1: 設定確認（Dry-run）

```bash
cd edu-creator
source .venv/bin/activate

python script/capture_screenshots.py \
  --config ../edu-config.yaml \
  --dry-run
```

**出力:**
```
📸 Screenshot Capture Plan:
   App: npm run dev
   Port: 3000
    Output: material/screenshot
   Total captures: 5
   - day01_step01: 初期表示 (/)
   - day01_step02: ダッシュボード (/dashboard/tasks)
   ...
```

### Step 2: 実際に撮影

```bash
python script/capture_screenshots.py \
  --config ../edu-config.yaml
```

**出力:**
```
📸 Capturing: 初期表示
   ✅ Saved to day01_step01_initial.png
📸 Capturing: ダッシュボード
   ✅ Saved to day01_step02_dashboard.png
...

============================================================
✅ Captured 5 screenshots
📁 Output directory: /path/to/material/screenshot
============================================================
```

### Step 3: メタデータ確認

```bash
cat material/screenshot/metadata.json
```

```json
[
  {
    "id": "day01_step01",
    "label": "初期表示",
    "filename": "day01_step01_initial.png",
    "url": "/",
    "viewport": {"width": 1280, "height": 720},
    "captured_at": "2025-01-25T10:30:45.123456",
    "app_version": "task-app v0.1.0"
  },
  ...
]
```

### Step 4: チュートリアル生成で自動埋め込み

```bash
python main.py \
  --config ../edu-config.yaml \
  --chapters 1
```

→ Scribe がスクショ参照を自動埋め込み
→ Validator が実ファイル存在確認
→ 不足あれば修正指示

---

## 8. 品質チェック連携

### Quality Checker に追加

```python
def check_all(self):
    return {
        ...existing checks...
        "screenshot_files": self.check_screenshot_files(),
    }

def check_screenshot_files(self) -> dict[str, any]:
    """スクショファイルの実在確認"""
    # material/screenshot/ に必要なファイルがあるか
    screenshot_refs = re.findall(r'!\[.*?\]\(\.\/screenshot\/([^)]+)\)', self.content)

    missing = []
    for ref in screenshot_refs:
        # ファイル実在確認
        if not Path(f"material/screenshot/{ref}").exists():
            missing.append(ref)

    return {
        "passed": len(missing) == 0,
        "issues": [f"❌ Screenshot not found: {f}" for f in missing]
    }
```

---

## 9. メリット・デメリット

### メリット ✅

1. **客観的**: AI の判定ではなく、実際のアプリで撮影
2. **信頼性**: ブラウザで確実に動作確認できる
3. **自動化**: 手動でスクショ撮影する手間がない
4. **メタデータ**: 撮影時刻、ビューポート等を記録（後で参考に）
5. **スケーラビリティ**: チャプター数増加時も config 追加するだけ

### デメリット・制限 ❌

1. **環境依存**: app が起動できる環境が必須（CI/CD では docker 環境等）
2. **時間がかかる**: ブラウザ起動・撮影に数秒〜数十秒
3. **認証**: ログイン必要な画面は `setup_script` で頑張る必要がある
4. **ダイナミックコンテンツ**: API遅延等でタイミング依存になる可能性

---

## 10. 実装の優先度

### Phase 1（基本）

- ✅ ScreenshotConfig/ScreenshotCaptureSpec モデル定義
- ✅ ScreenshotCapture 実装（単純なケース）
- ✅ CLI: capture_screenshots.py
- ✅ quality_checker に check_screenshot_files() 追加

### Phase 2（拡張）

- 認証サポート（login → capture flow）
- メタデータの活用（撮影失敗時の自動リトライ等）
- 並列撮影（複数ブラウザ同時実行）

### Phase 3（統合）

- main.py へのフル統合
- Scribe からの自動埋め込み
- Validator との連携強化

---

## 11. 依存関係

```toml
# pyproject.toml に追加

[project.optional-dependencies]
screenshot = [
    "playwright>=1.40.0",
]
```

インストール:
```bash
pip install -e ".[screenshot]"
playwright install chromium
```

---

## 次のステップ

1. 設計確認（オーナーからの OK）
2. Phase 1 実装
3. task-app で試験撮影
4. Phase 2, 3 順次実装

この設計でいけそうですか？修正・追加箇所あれば言ってください！
