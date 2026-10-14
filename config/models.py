from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError, model_validator

# =============================================================================
# 📸 Screenshot Configuration Models
# =============================================================================

class AppStartupConfig(BaseModel):
    command: str = "npm run dev"
    port: int = 3000
    wait_time_seconds: int = 20
    ready_pattern: str = ""

class AuthConfig(BaseModel):
    enabled: bool = False
    login_url: str = "/login"
    username: str = ""
    password: str = ""
    wait_for_redirect: str = "/dashboard"

class ScreenshotCaptureSpec(BaseModel):
    id: str
    label: str
    url: str
    viewport_width: int = 1280
    viewport_height: int = 720
    full_page: bool = False
    setup_script: Optional[str] = None
    wait_for_selector: Optional[str] = None

class ScreenshotConfig(BaseModel):
    enabled: bool = False
    app_startup: AppStartupConfig = Field(default_factory=AppStartupConfig)
    headless: bool = True
    slow_motion_ms: int = 0
    auth: AuthConfig = Field(default_factory=AuthConfig)
    captures: List[ScreenshotCaptureSpec] = Field(default_factory=list)
    output_dir: str = "material/screenshot"
    filename_pattern: str = "{id}.png"
    metadata_file: str = "metadata.json"

# =============================================================================
# ⚙️ General Configuration Models
# =============================================================================

class SafetyConfig(BaseModel):
    max_iterations: int = 3
    max_retries: int = 3
    max_rpm: int = 10
    timeout_seconds: int = 1800
    cost_confirmation_threshold_usd: float = 1.0

class ExclusionConfig(BaseModel):
    directories: List[str] = Field(default_factory=lambda: [
        "node_modules", ".next", "dist", "build", "coverage",
        ".git", ".vercel", "playwright-report", "test-results",
        ".idea", "__pycache__", ".pnp", "out", "edu-creator"
    ])
    patterns: List[str] = Field(default_factory=lambda: [
        "*.log", "*.env*", "*.db", "*.db-*", "*.local", "*.pem", "*.py"
    ])

class LLMConfig(BaseModel):
    commander_model: str = "gpt-4-turbo"
    worker_model: str = "gemini-1.5-flash"
    commander_temperature: float = 0.2
    worker_temperature: float = 0.4

class PathsConfig(BaseModel):
    src_dir: str = "src"
    output_dir: str = "material/30days-curriculum"

class AppConfig(BaseModel):
    log_dir: str = "logs"
    log_level: str = "INFO"
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    exclusions: ExclusionConfig = Field(default_factory=ExclusionConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    screenshots: ScreenshotConfig = Field(default_factory=ScreenshotConfig)
    paths: Optional[PathsConfig] = None

    # Allow extra fields for custom configurations
    model_config = {"extra": "allow"}

def validate_config(config: dict[str, Any]) -> Tuple[bool, Optional[AppConfig], Optional[str]]:
    """
    Validate the configuration dictionary against the AppConfig Pydantic model.

    Args:
        config: The configuration dictionary to validate.

    Returns:
        A tuple containing:
        - bool: True if validation succeeded, False otherwise.
        - Optional[AppConfig]: The validated configuration object if successful, None otherwise.
        - Optional[str]: An error message if validation failed, None otherwise.
    """
    try:
        validated_config = AppConfig(**config)
        return True, validated_config, None
    except ValidationError as e:
        return False, None, str(e)
    except Exception as e:
        return False, None, f"Unexpected validation error: {e}"
