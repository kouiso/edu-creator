import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from config.models import AppConfig, validate_config
except ImportError:
    validate_config = None
    AppConfig = None

try:
    import main as main_module
    from main import CachedFileReadTool as MainCachedFileReadTool
    from main import FileCache as MainFileCache
except ImportError:
    main_module = None
    MainCachedFileReadTool = None
    MainFileCache = None

class TestSmoke(unittest.TestCase):
    def test_01_import_config_models(self):
        """config_modelsがインポートできるか確認"""
        self.assertIsNotNone(validate_config, "Failed to import validate_config from config_models")
        self.assertIsNotNone(AppConfig, "Failed to import AppConfig from config_models")

    def test_02_validate_config(self):
        """設定バリデーションの動作確認"""
        if validate_config is None:
            self.skipTest("config_models not imported")

        dummy_config = {
            "log_level": "DEBUG",
            "safety": {
                "max_iterations": 5
            }
        }
        success, model, error = validate_config(dummy_config)
        self.assertTrue(success, f"Validation failed: {error}")
        self.assertIsInstance(model, AppConfig)
        self.assertEqual(model.safety.max_iterations, 5)
        # Default values
        self.assertEqual(model.safety.max_retries, 3)

    def test_03_main_help(self):
        """main.py --help が動作するか確認"""
        main_script = Path(__file__).parent.parent / "main.py"
        result = subprocess.run(
            [sys.executable, str(main_script), "--help"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, f"main.py --help failed: {result.stderr}")
        self.assertIn("usage:", result.stdout)

    def test_04_main_cached_file_read_tool_unwraps_container_line_args(self):
        """main.py版CachedFileReadToolでもコンテナ包みのstart_line/line_countを正しく解除できるか確認"""
        if MainCachedFileReadTool is None:
            self.skipTest("main.CachedFileReadTool not imported")

        tool = MainCachedFileReadTool()
        file_path, start_line, line_count = tool._normalize_args(
            "x.py", [5], ("3",)
        )
        self.assertEqual((file_path, start_line, line_count), ("x.py", 5, 3))

    def test_05_main_cached_partial_read_preserves_line_endings(self):
        """main.py版のキャッシュ経由の部分読み込みでも改行が保持されるか確認"""
        if MainCachedFileReadTool is None or main_module is None:
            self.skipTest("main.CachedFileReadTool not imported")

        with tempfile.TemporaryDirectory() as td:
            cache_file = str(Path(td) / ".cache.json")
            main_module._file_cache = MainFileCache(cache_file=cache_file, enabled=True)
            dummy_file = Path(td) / "dummy.txt"
            dummy_file.write_text("a\nb\nc\n", encoding="utf-8")

            tool = MainCachedFileReadTool()
            miss = tool._run(file_path=str(dummy_file), start_line=1, line_count=1)
            hit = tool._run(file_path=str(dummy_file), start_line=1, line_count=1)
            self.assertEqual(miss, hit)
            self.assertEqual(hit, "a\n")

if __name__ == "__main__":
    unittest.main()
