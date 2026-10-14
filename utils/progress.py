import time
from datetime import datetime, timedelta


class ProgressTracker:
    """
    Track progress and estimate remaining time for chapter generation.

    チャプター生成の進捗を追跡し、残り時間を推定する。
    """

    def __init__(self, total_chapters: int, tasks_per_chapter: int = 4):
        """
        Initialize progress tracker.

        Args:
            total_chapters: Total number of chapters to generate
            tasks_per_chapter: Number of tasks per chapter (default: 4 - research, outline, write, review)
        """
        self.total_chapters = total_chapters
        self.tasks_per_chapter = tasks_per_chapter
        self.total_tasks = total_chapters * tasks_per_chapter

        self.start_time: float | None = None
        self.chapter_times: list[float] = []
        self.current_chapter = 0
        self.current_task = 0

        # 最初のチャプターの推定時間（秒）- 実測後に更新
        # Estimated time for first chapter (seconds) - updated after measurement
        self.estimated_chapter_time = 300  # 5分をデフォルト推定

    def start(self) -> None:
        """Start the progress tracker."""
        self.start_time = time.time()
        self._print_header()

    def _print_header(self) -> None:
        """Print initial progress header."""
        print("\n" + "=" * 70)
        print("⏱️  PROGRESS TRACKER")
        print("=" * 70)
        print(f"📚 Total chapters: {self.total_chapters}")
        print(f"📝 Tasks per chapter: {self.tasks_per_chapter}")
        print(f"🕐 Started at: {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 70 + "\n")

    def start_chapter(self, chapter_num: int, chapter_title: str) -> float:
        """
        Mark the start of a chapter and return start time.

        チャプターの開始をマークし、開始時刻を返す。
        """
        self.current_chapter = chapter_num
        chapter_start = time.time()

        # 推定残り時間を計算
        remaining_chapters = self.total_chapters - chapter_num + 1
        if self.chapter_times:
            avg_time = sum(self.chapter_times) / len(self.chapter_times)
            estimated_remaining = avg_time * remaining_chapters
        else:
            estimated_remaining = self.estimated_chapter_time * remaining_chapters

        eta = datetime.now() + timedelta(seconds=estimated_remaining)

        print("\n" + "╔" + "═" * 68 + "╗")
        print(f"║ 📚 Chapter {chapter_num}/{self.total_chapters}: {chapter_title[:50]:<50} ║")
        print("╠" + "═" * 68 + "╣")
        print(f"║ ⏱️  Estimated remaining: {self._format_duration(estimated_remaining):<43} ║")
        print(f"║ 🏁 ETA: {eta.strftime('%H:%M:%S'):<55} ║")
        print("╚" + "═" * 68 + "╝\n")

        return chapter_start

    def end_chapter(self, chapter_start: float) -> None:
        """
        Mark the end of a chapter and update statistics.

        チャプターの終了をマークし、統計を更新する。
        """
        chapter_duration = time.time() - chapter_start
        self.chapter_times.append(chapter_duration)

        # 次回の推定時間を更新
        self.estimated_chapter_time = sum(self.chapter_times) / len(self.chapter_times)

        print(f"\n✅ Chapter completed in {self._format_duration(chapter_duration)}")

    def print_task_progress(self, task_name: str, task_num: int) -> None:
        """
        Print progress for current task.

        現在のタスクの進捗を表示する。
        """
        total_tasks_done = (self.current_chapter - 1) * self.tasks_per_chapter + task_num
        overall_progress = (total_tasks_done / self.total_tasks) * 100

        elapsed = time.time() - (self.start_time or time.time())
        if total_tasks_done > 0:
            estimated_total = elapsed / total_tasks_done * self.total_tasks
            remaining = estimated_total - elapsed
        else:
            remaining = self.estimated_chapter_time * self.total_chapters

        progress_bar = self._create_progress_bar(overall_progress)

        print(f"├── 📋 Task {task_num}/{self.tasks_per_chapter}: {task_name}")
        print(f"│   {progress_bar} {overall_progress:.1f}%")
        print(f"│   ⏱️  Remaining: ~{self._format_duration(remaining)}")

    def print_final_summary(self) -> None:
        """Print final summary after all chapters are complete."""
        if not self.start_time:
            return

        total_duration = time.time() - self.start_time
        avg_chapter_time = sum(self.chapter_times) / len(self.chapter_times) if self.chapter_times else 0

        print("\n" + "═" * 70)
        print("🎉 GENERATION COMPLETE!")
        print("═" * 70)
        print(f"📚 Chapters generated: {len(self.chapter_times)}/{self.total_chapters}")
        print(f"⏱️  Total time: {self._format_duration(total_duration)}")
        print(f"📊 Average per chapter: {self._format_duration(avg_chapter_time)}")
        print(f"🏁 Finished at: {datetime.now().strftime('%H:%M:%S')}")
        print("═" * 70 + "\n")

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}分{secs}秒"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}時間{minutes}分"

    def _create_progress_bar(self, percentage: float, width: int = 30) -> str:
        """Create a visual progress bar."""
        filled = int(width * percentage / 100)
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}]"
