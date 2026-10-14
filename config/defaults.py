import os

DEFAULT_CONFIG = {
    "log_dir": "logs",
    "log_level": "INFO",
    "safety": {
        "max_iterations": 3,
        "max_retries": 3,
        "max_rpm": 10,
        "timeout_seconds": 1800,
        "cost_confirmation_threshold_usd": 1.0,
    },
    "exclusions": {
        "directories": [
            "node_modules", ".next", "dist", "build", "coverage",
            ".git", ".vercel", "playwright-report", "test-results",
            ".idea", "__pycache__", ".pnp", "out", "edu-creator",
        ],
        "patterns": ["*.log", "*.env*", "*.db", "*.db-*", "*.local", "*.pem", "*.py"],
    },
    "llm": {
        "commander_model": os.getenv("OPENAI_MODEL", "gpt-5.2"),
        "worker_model": os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"),
        "commander_temperature": 0.2,
        "worker_temperature": 0.4,
    },
    "screenshots": {
        "enabled": False,
        "app_startup": {
            "command": "npm run dev",
            "port": 3000,
            "wait_time_seconds": 20,
            "ready_pattern": "",
        },
        "headless": True,
        "slow_motion_ms": 0,
        "auth": {
            "enabled": False,
            "login_url": "/login",
            "username": "",
            "password": "",
            "wait_for_redirect": "/dashboard",
        },
        "captures": [],
        "output_dir": "material/screenshot",
        "filename_pattern": "{id}.png",
        "metadata_file": "metadata.json",
    },
}
