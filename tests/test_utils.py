import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from utils.cache import CachedFileReadTool, get_cache, init_cache
from utils.cost import estimate_cost
from utils.logger import TeeOutput
from utils.progress import ProgressTracker


class TestUtils(unittest.TestCase):
    def test_cost_estimation(self):
        config = {}
        # Test case 1: 10 chapters
        result = estimate_cost(10, config)
        self.assertEqual(result["num_chapters"], 10)
        self.assertEqual(result["gpt_tokens"], 40000)
        self.assertEqual(result["gemini_tokens"], 500000)
        # 40k tokens * $0.03/1k = $1.20
        self.assertAlmostEqual(result["estimated_cost_usd"], 1.20)
        self.assertTrue(result["gemini_within_free_tier"])

        # Test case 2: 25 chapters (Gemini tokens > 1M)
        result = estimate_cost(25, config)
        self.assertEqual(result["num_chapters"], 25)
        self.assertEqual(result["gemini_tokens"], 1250000)
        self.assertFalse(result["gemini_within_free_tier"])

    def test_progress_tracker(self):
        tracker = ProgressTracker(total_chapters=2, tasks_per_chapter=4)
        self.assertEqual(tracker.total_tasks, 8)

        # Capture stdout
        with patch("sys.stdout", new_callable=MagicMock) as mock_stdout:
             tracker.start()
             tracker.start_chapter(1, "Test Chapter 1")
             tracker.print_task_progress("Task 1", 1)
             tracker.end_chapter(tracker.start_time)
             # Basic check to ensure no errors and methods run
             self.assertIsNotNone(tracker.start_time)

    def test_tee_output(self):
        mock_console = MagicMock()
        mock_file = MagicMock()
        tee = TeeOutput(mock_console, mock_file)

        tee.write("test message")
        mock_console.write.assert_called_with("test message")
        mock_file.write.assert_called_with("test message")

        tee.flush()
        mock_console.flush.assert_called()
        mock_file.flush.assert_called()

    def test_cache_initialization(self):
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            cache_file = temp_dir / ".test_cache.json"

            # Create a dummy file to cache
            dummy_file = temp_dir / "dummy.txt"
            dummy_file.write_text("Hello Cache", encoding="utf-8")

            # Init cache
            init_cache(cache_file=str(cache_file), enabled=True)
            cache = get_cache()

            self.assertIsNotNone(cache)
            self.assertTrue(cache.enabled)

            # Test set
            cache.set(str(dummy_file), "Hello Cache Content")

            # Test get
            cached_content = cache.get(str(dummy_file))
            self.assertEqual(cached_content, "Hello Cache Content")

            # Test invalidation (modify file)
            # update file mtime (and content)
            import os
            import time
            time.sleep(0.1)  # Ensure mtime is different
            dummy_file.write_text("Modified Content", encoding="utf-8")

            # Should be None because mtime changed and cache checks actual file mtime
            self.assertIsNone(cache.get(str(dummy_file)))

    def test_normalize_args_unwraps_container_line_args(self):
        tool = CachedFileReadTool()

        file_path, start_line, line_count = tool._normalize_args(
            "x.py", [5], ("3",)
        )
        self.assertEqual((file_path, start_line, line_count), ("x.py", 5, 3))

        file_path, start_line, line_count = tool._normalize_args(
            {"file_path": "x.py", "start_line": [5], "line_count": ["3"]}
        )
        self.assertEqual((file_path, start_line, line_count), ("x.py", 5, 3))

    def test_normalize_args_falls_back_on_unresolvable_container(self):
        tool = CachedFileReadTool()

        file_path, start_line, line_count = tool._normalize_args(
            "x.py", [], []
        )
        self.assertEqual((file_path, start_line, line_count), ("x.py", 1, None))

    def test_cached_partial_read_preserves_line_endings(self):
        with tempfile.TemporaryDirectory() as td:
            cache_file = str(Path(td) / ".cache.json")
            init_cache(cache_file=cache_file, enabled=True)
            dummy_file = Path(td) / "dummy.txt"
            dummy_file.write_text("a\nb\nc\n", encoding="utf-8")

            tool = CachedFileReadTool()
            miss = tool._run(file_path=str(dummy_file), start_line=1, line_count=1)
            hit = tool._run(file_path=str(dummy_file), start_line=1, line_count=1)
            self.assertEqual(miss, hit)
            self.assertEqual(hit, "a\n")

    def test_cached_partial_read_out_of_range_returns_error(self):
        with tempfile.TemporaryDirectory() as td:
            cache_file = str(Path(td) / ".cache.json")
            init_cache(cache_file=cache_file, enabled=True)
            dummy_file = Path(td) / "dummy.txt"
            dummy_file.write_text("a\nb\nc\n", encoding="utf-8")

            tool = CachedFileReadTool()
            tool._run(file_path=str(dummy_file))
            result = tool._run(file_path=str(dummy_file), start_line=100, line_count=1)
            self.assertTrue(result.startswith("Error:"))

if __name__ == "__main__":
    unittest.main()
