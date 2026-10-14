import json
import os
from pathlib import Path
from typing import Any, Optional

from crewai_tools import FileReadTool


class FileCache:
    """
    Simple file cache with automatic invalidation based on mtime.
    ファイル更新時刻に基づく自動無効化付きファイルキャッシュ。
    """

    def __init__(self, cache_file: str = ".file_cache.json", enabled: bool = True):
        self.cache_file = Path(cache_file)
        self.enabled = enabled
        self.cache: dict[str, dict[str, Any]] = {}
        self.stats = {"hits": 0, "misses": 0, "invalidations": 0}
        self._load()

    def _load(self) -> None:
        """Load cache from disk if exists."""
        if not self.enabled:
            return

        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception as e:
                print(f"⚠️  Failed to load cache: {e}")
                self.cache = {}

    def _save(self) -> None:
        """Save cache to disk."""
        if not self.enabled:
            return

        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  Failed to save cache: {e}")

    def get(self, file_path: str) -> Optional[str]:
        """
        Get file content from cache if valid.
        ファイルがキャッシュにあり、更新されていなければ内容を返す。
        """
        if not self.enabled:
            return None

        abs_path = str(Path(file_path).resolve())

        # ファイルが存在しない場合はキャッシュも無効
        if not Path(abs_path).exists():
            return None

        # ファイルの最終更新時刻を取得
        try:
            current_mtime = os.path.getmtime(abs_path)
        except OSError:
            return None

        # キャッシュに存在するか確認
        if abs_path in self.cache:
            cached_mtime = self.cache[abs_path].get("mtime")
            if cached_mtime == current_mtime:
                # キャッシュヒット
                self.stats["hits"] += 1
                return self.cache[abs_path]["content"]
            else:
                # ファイルが更新されているので無効化
                self.stats["invalidations"] += 1
                del self.cache[abs_path]

        # キャッシュミス
        self.stats["misses"] += 1
        return None

    def set(self, file_path: str, content: str) -> None:
        """
        Store file content in cache with mtime.
        ファイル内容とmtimeをキャッシュに保存。
        """
        if not self.enabled:
            return

        abs_path = str(Path(file_path).resolve())

        try:
            mtime = os.path.getmtime(abs_path)
            self.cache[abs_path] = {"content": content, "mtime": mtime}
            self._save()
        except OSError as e:
            print(f"⚠️  Failed to cache {file_path}: {e}")

    def clear(self) -> None:
        """Clear all cache."""
        self.cache = {}
        self.stats = {"hits": 0, "misses": 0, "invalidations": 0}
        if self.cache_file.exists():
            self.cache_file.unlink()

    def print_stats(self) -> None:
        """Print cache statistics."""
        if not self.enabled:
            print("📦 Cache: Disabled")
            return

        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0

        print("\n" + "=" * 60)
        print("📦 File Cache Statistics")
        print("=" * 60)
        print(f"   Cache hits: {self.stats['hits']}")
        print(f"   Cache misses: {self.stats['misses']}")
        print(f"   Auto invalidations: {self.stats['invalidations']}")
        print(f"   Hit rate: {hit_rate:.1f}%")
        print(f"   Total cached files: {len(self.cache)}")
        print("=" * 60 + "\n")


# Global cache instance
_file_cache: Optional[FileCache] = None

def init_cache(cache_file: str = ".file_cache.json", enabled: bool = True) -> None:
    global _file_cache
    _file_cache = FileCache(cache_file, enabled)

def get_cache() -> Optional[FileCache]:
    return _file_cache

class CachedFileReadTool(FileReadTool):
    """
    FileReadTool with automatic caching.
    自動キャッシュ付きFileReadTool。
    """

    def _normalize_args(
        self,
        file_path: Any = None,
        start_line: Any = 1,
        line_count: Any = None,
    ) -> tuple[str | None, int, int | None]:
        if isinstance(file_path, dict):
            args = file_path
            file_path = args.get("file_path") or args.get("path")
            start_line = args.get("start_line", start_line)
            line_count = args.get("line_count", line_count)
        elif isinstance(file_path, (tuple, list)):
            for item in file_path:
                if isinstance(item, dict):
                    return self._normalize_args(item, start_line, line_count)
                if isinstance(item, str):
                    file_path = item
                    break

        if file_path is not None and not isinstance(file_path, str):
            file_path = str(file_path)

        start_line = self._unwrap_scalar(start_line)
        line_count = self._unwrap_scalar(line_count)

        try:
            normalized_start_line = int(start_line or 1)
        except (TypeError, ValueError):
            normalized_start_line = 1

        try:
            normalized_line_count = int(line_count) if line_count is not None else None
        except (TypeError, ValueError):
            normalized_line_count = None

        return file_path, normalized_start_line, normalized_line_count

    @staticmethod
    def _unwrap_scalar(value: Any) -> Any:
        """dict/tuple/listで渡ってきた値から、その中身のスカラー値を取り出す。

        Toolの引数はLLM側の呼び出し形式によりコンテナで包まれて届くことがあり、
        素通しでint()に渡すと変換に失敗して既定値へ黙って落ちてしまう
        （start_lineは1、line_countはNone＝ファイル全体扱いになる）。
        """
        if isinstance(value, dict):
            for key in ("value", "start_line", "line_count"):
                if key in value:
                    return value[key]
            return next(iter(value.values()), None) if value else None
        if isinstance(value, (tuple, list)):
            return value[0] if value else None
        return value

    def _run(
        self,
        file_path: Any = None,
        start_line: Any = 1,
        line_count: Any = None,
    ) -> str:
        """Override _run to add caching layer."""
        global _file_cache

        file_path, start_line, line_count = self._normalize_args(
            file_path or self.file_path,
            start_line,
            line_count,
        )

        if not file_path:
            raise ValueError("file_path must be provided")

        # キャッシュが有効かつ存在する場合
        if _file_cache and _file_cache.enabled:
            cached_content = _file_cache.get(file_path)
            if cached_content is not None:
                if start_line or line_count:
                    lines = cached_content.splitlines(keepends=True)
                    start_idx = max((start_line - 1) if start_line else 0, 0)
                    end_idx = (start_idx + line_count) if line_count else len(lines)
                    selected_lines = lines[start_idx:end_idx]
                    if not selected_lines and start_idx > 0:
                        return f"Error: Start line {start_line} exceeds the number of lines in the file."
                    return "".join(selected_lines)
                return cached_content

        # キャッシュミス → 実際にファイルを読む
        content = super()._run(
            file_path=file_path,
            start_line=start_line,
            line_count=line_count,
        )

        # キャッシュに保存
        if _file_cache and _file_cache.enabled:
            if start_line != 1 or line_count is not None:
                full_content = super()._run(file_path=file_path, start_line=1, line_count=None)
                _file_cache.set(file_path, full_content)
            else:
                _file_cache.set(file_path, content)

        return content
