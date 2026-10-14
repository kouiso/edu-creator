import io
import logging
import sys
from pathlib import Path


def setup_logging_for_chapter(chapter_log_dir: Path, log_level: str = "INFO") -> tuple[logging.FileHandler, io.StringIO]:
    """
    Setup logging handlers for chapter execution.

    Returns: (file_handler, string_buffer)
    - file_handler: ファイルに出力するハンドラー
    - string_buffer: 画面とファイルの両方に出力するためのバッファー

    Creates:
    - logs/day01/crew_output.log: CrewAI verbose output
    """
    # Create logger for chapter
    chapter_logger = logging.getLogger(f"chapter_{chapter_log_dir.name}")
    chapter_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    chapter_logger.handlers = []

    # File handler for crew_output.log
    log_file = chapter_log_dir / "crew_output.log"
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    chapter_logger.addHandler(file_handler)

    # StringIO buffer for console + file dual output
    string_buffer = io.StringIO()

    return file_handler, string_buffer


class TeeOutput:
    """Tee stdout to both console and file"""
    def __init__(self, console, log_file):
        self.console = console
        self.log_file = log_file

    def write(self, text):
        self.console.write(text)
        self.console.flush()
        if self.log_file:
            self.log_file.write(text)
            self.log_file.flush()

    def flush(self):
        self.console.flush()
        if self.log_file:
            self.log_file.flush()

    def isatty(self):
        return self.console.isatty()
