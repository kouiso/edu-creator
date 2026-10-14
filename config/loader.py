import copy
import os
from pathlib import Path
from typing import Any

import yaml

from .defaults import DEFAULT_CONFIG
from .models import validate_config


def _deep_merge(base: Any, override: Any) -> Any:
    """Recursively merge dictionaries."""
    if isinstance(base, dict) and isinstance(override, dict):
        merged = base.copy()
        for key, value in override.items():
            merged[key] = _deep_merge(merged.get(key), value)
        return merged

    if override is None:
        return base

    return override

def load_config(config_path: str) -> dict[str, Any]:
    """
    Load config from defaults + environment config + user yaml + validation.
    
    Priority (後から読み込むものが優先):
    1. DEFAULT_CONFIG (config/defaults.py)
    2. Environment config (dev-config.yaml or prod-config.yaml)
    3. User config (edu-config.yaml)
    
    Environment selection:
    - EDU_ENV=dev  → config/dev-config.yaml
    - EDU_ENV=prod → config/prod-config.yaml
    - EDU_ENV未設定 → 環境設定なし（デフォルト＋ユーザー設定のみ）
    """
    config: dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
    
    # 1. 環境別設定の読み込み（EDU_ENV環境変数）
    env = os.getenv("EDU_ENV", "").lower()
    if env in ("dev", "prod"):
        env_config_path = Path(__file__).parent / f"{env}-config.yaml"
        if env_config_path.exists():
            print(f"📌 Loading environment config: {env_config_path}")
            with open(env_config_path, "r", encoding="utf-8") as f:
                env_config = yaml.safe_load(f) or {}
            config = _deep_merge(config, env_config)
        else:
            print(f"⚠️ EDU_ENV={env} but {env_config_path} not found. Skipping.")
    
    # 2. ユーザー設定の読み込み（最優先）
    if config_path and Path(config_path).exists():
        print(f"📌 Loading user config: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, user_config)

    # 3. Pydantic検証
    success, validated, error = validate_config(config)
    if not success or validated is None:
        raise ValueError(error)

    validated_dict = validated.model_dump()

    # Preserve extra fields not in Pydantic model
    for key, value in config.items():
        if key not in validated_dict:
            validated_dict[key] = value

    return validated_dict
