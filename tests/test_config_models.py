"""
Config Models のテスト

Pydantic 設定モデルのバリデーションを検証する。
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.models import (
    AppConfig,
    AuthConfig,
    ExclusionConfig,
    LLMConfig,
    PathsConfig,
    SafetyConfig,
    ScreenshotCaptureSpec,
    ScreenshotConfig,
    validate_config,
)


class TestSafetyConfig:
    """SafetyConfig のテスト"""

    def test_defaults(self):
        """デフォルト値"""
        config = SafetyConfig()
        assert config.max_iterations == 3
        assert config.max_retries == 3
        assert config.max_rpm == 10
        assert config.timeout_seconds == 1800
        assert config.cost_confirmation_threshold_usd == 1.0

    def test_custom_values(self):
        """カスタム値"""
        config = SafetyConfig(
            max_iterations=10,
            max_retries=5,
            max_rpm=20,
            timeout_seconds=3600,
            cost_confirmation_threshold_usd=5.0,
        )
        assert config.max_iterations == 10
        assert config.max_retries == 5
        assert config.max_rpm == 20
        assert config.timeout_seconds == 3600
        assert config.cost_confirmation_threshold_usd == 5.0


class TestExclusionConfig:
    """ExclusionConfig のテスト"""

    def test_defaults(self):
        """デフォルト値"""
        config = ExclusionConfig()
        assert "node_modules" in config.directories
        assert ".git" in config.directories
        assert "*.log" in config.patterns
        assert "*.env*" in config.patterns

    def test_custom_directories(self):
        """カスタムディレクトリ"""
        config = ExclusionConfig(directories=["custom_dir", "another_dir"])
        assert config.directories == ["custom_dir", "another_dir"]

    def test_custom_patterns(self):
        """カスタムパターン"""
        config = ExclusionConfig(patterns=["*.tmp", "*.bak"])
        assert config.patterns == ["*.tmp", "*.bak"]


class TestLLMConfig:
    """LLMConfig のテスト"""

    def test_defaults(self):
        """デフォルト値"""
        config = LLMConfig()
        assert config.commander_model == "gpt-4-turbo"
        assert config.worker_model == "gemini-1.5-flash"
        assert config.commander_temperature == 0.2
        assert config.worker_temperature == 0.4

    def test_custom_models(self):
        """カスタムモデル"""
        config = LLMConfig(
            commander_model="gpt-4o",
            worker_model="gemini-2.0-flash",
            commander_temperature=0.1,
            worker_temperature=0.5,
        )
        assert config.commander_model == "gpt-4o"
        assert config.worker_model == "gemini-2.0-flash"
        assert config.commander_temperature == 0.1
        assert config.worker_temperature == 0.5


class TestPathsConfig:
    """PathsConfig のテスト"""

    def test_defaults(self):
        """デフォルト値"""
        config = PathsConfig()
        assert config.src_dir == "src"
        assert config.output_dir == "material/30days-curriculum"

    def test_custom_paths(self):
        """カスタムパス"""
        config = PathsConfig(src_dir="source", output_dir="output/tutorials")
        assert config.src_dir == "source"
        assert config.output_dir == "output/tutorials"


class TestAuthConfig:
    """AuthConfig のテスト"""

    def test_defaults(self):
        """デフォルト値"""
        config = AuthConfig()
        assert config.enabled is False
        assert config.login_url == "/login"
        assert config.username == ""
        assert config.password == ""
        assert config.wait_for_redirect == "/dashboard"

    def test_enabled_auth(self):
        """認証有効化"""
        config = AuthConfig(
            enabled=True,
            login_url="/auth/login",
            username="testuser",
            password="testpass",
            wait_for_redirect="/home",
        )
        assert config.enabled is True
        assert config.login_url == "/auth/login"
        assert config.username == "testuser"


class TestScreenshotCaptureSpec:
    """ScreenshotCaptureSpec のテスト"""

    def test_required_fields(self):
        """必須フィールド"""
        spec = ScreenshotCaptureSpec(
            id="login",
            label="Login Page",
            url="/login",
        )
        assert spec.id == "login"
        assert spec.label == "Login Page"
        assert spec.url == "/login"

    def test_defaults(self):
        """デフォルト値"""
        spec = ScreenshotCaptureSpec(
            id="test",
            label="Test",
            url="/test",
        )
        assert spec.viewport_width == 1280
        assert spec.viewport_height == 720
        assert spec.full_page is False
        assert spec.setup_script is None
        assert spec.wait_for_selector is None

    def test_full_customization(self):
        """フルカスタマイズ"""
        spec = ScreenshotCaptureSpec(
            id="dashboard",
            label="Dashboard",
            url="/dashboard",
            viewport_width=1920,
            viewport_height=1080,
            full_page=True,
            setup_script="document.body.classList.add('dark')",
            wait_for_selector=".dashboard-loaded",
        )
        assert spec.viewport_width == 1920
        assert spec.viewport_height == 1080
        assert spec.full_page is True
        assert spec.setup_script is not None
        assert spec.wait_for_selector == ".dashboard-loaded"


class TestScreenshotConfig:
    """ScreenshotConfig のテスト"""

    def test_defaults(self):
        """デフォルト値"""
        config = ScreenshotConfig()
        assert config.enabled is False
        assert config.headless is True
        assert config.slow_motion_ms == 0
        assert config.output_dir == "material/screenshot"
        assert config.filename_pattern == "{id}.png"
        assert config.metadata_file == "metadata.json"
        assert config.captures == []

    def test_with_captures(self):
        """キャプチャ設定付き"""
        captures = [
            ScreenshotCaptureSpec(id="page1", label="Page 1", url="/page1"),
            ScreenshotCaptureSpec(id="page2", label="Page 2", url="/page2"),
        ]
        config = ScreenshotConfig(enabled=True, captures=captures)
        assert config.enabled is True
        assert len(config.captures) == 2
        assert config.captures[0].id == "page1"


class TestAppConfig:
    """AppConfig のテスト"""

    def test_defaults(self):
        """デフォルト値"""
        config = AppConfig()
        assert config.log_dir == "logs"
        assert config.log_level == "INFO"
        assert config.safety is not None
        assert config.exclusions is not None
        assert config.llm is not None
        assert config.screenshots is not None
        assert config.paths is None

    def test_minimal_config(self):
        """最小構成"""
        config = AppConfig(log_level="DEBUG")
        assert config.log_level == "DEBUG"
        # デフォルトのネスト設定が存在
        assert config.safety.max_iterations == 3

    def test_with_nested_configs(self):
        """ネスト設定付き"""
        config = AppConfig(
            log_level="DEBUG",
            safety=SafetyConfig(max_iterations=10),
            llm=LLMConfig(commander_model="gpt-4o"),
            paths=PathsConfig(src_dir="custom_src"),
        )
        assert config.log_level == "DEBUG"
        assert config.safety.max_iterations == 10
        assert config.llm.commander_model == "gpt-4o"
        assert config.paths.src_dir == "custom_src"

    def test_extra_fields_allowed(self):
        """追加フィールドが許可される"""
        config = AppConfig(custom_field="custom_value")
        # model_config で extra = "allow" が設定されている
        assert hasattr(config, "custom_field")
        assert config.custom_field == "custom_value"


class TestValidateConfig:
    """validate_config() のテスト"""

    def test_empty_config(self):
        """空の設定"""
        success, model, error = validate_config({})
        assert success is True
        assert model is not None
        assert error is None
        # デフォルト値が適用される
        assert model.log_level == "INFO"

    def test_valid_config(self):
        """有効な設定"""
        success, model, error = validate_config({
            "log_level": "DEBUG",
            "log_dir": "custom_logs",
        })
        assert success is True
        assert model is not None
        assert error is None
        assert model.log_level == "DEBUG"
        assert model.log_dir == "custom_logs"

    def test_valid_nested_config(self):
        """有効なネスト設定"""
        success, model, error = validate_config({
            "safety": {
                "max_iterations": 5,
                "max_retries": 2,
            },
            "llm": {
                "commander_model": "gpt-4o",
            },
        })
        assert success is True
        assert model.safety.max_iterations == 5
        assert model.safety.max_retries == 2
        assert model.llm.commander_model == "gpt-4o"

    def test_invalid_type(self):
        """型エラー"""
        success, model, error = validate_config({
            "safety": {
                "max_iterations": "not a number",
            },
        })
        assert success is False
        assert model is None
        assert error is not None
        assert "max_iterations" in error.lower() or "validation" in error.lower()

    def test_invalid_nested_type(self):
        """ネスト設定の型エラー"""
        success, model, error = validate_config({
            "llm": {
                "commander_temperature": "high",  # should be float
            },
        })
        assert success is False
        assert model is None
        assert error is not None

    def test_screenshot_config_validation(self):
        """スクリーンショット設定のバリデーション"""
        success, model, error = validate_config({
            "screenshots": {
                "enabled": True,
                "headless": False,
                "captures": [
                    {
                        "id": "login",
                        "label": "Login Page",
                        "url": "/login",
                    },
                ],
            },
        })
        assert success is True
        assert model.screenshots.enabled is True
        assert model.screenshots.headless is False
        assert len(model.screenshots.captures) == 1
        assert model.screenshots.captures[0].id == "login"

    def test_complete_config(self):
        """完全な設定"""
        success, model, error = validate_config({
            "log_dir": "logs",
            "log_level": "DEBUG",
            "safety": {
                "max_iterations": 5,
                "max_retries": 3,
                "max_rpm": 15,
                "timeout_seconds": 2400,
                "cost_confirmation_threshold_usd": 2.0,
            },
            "exclusions": {
                "directories": ["node_modules", ".git", "custom"],
                "patterns": ["*.log", "*.tmp"],
            },
            "llm": {
                "commander_model": "gpt-4o",
                "worker_model": "gemini-2.0-flash",
                "commander_temperature": 0.15,
                "worker_temperature": 0.35,
            },
            "paths": {
                "src_dir": "source",
                "output_dir": "output",
            },
        })
        assert success is True
        assert model.log_level == "DEBUG"
        assert model.safety.max_iterations == 5
        assert model.exclusions.directories == ["node_modules", ".git", "custom"]
        assert model.llm.commander_model == "gpt-4o"
        assert model.paths.src_dir == "source"
