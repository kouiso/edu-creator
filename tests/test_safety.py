"""
PathCompliance のテスト

パス安全性検証機能を検証する。
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.safety import PathCompliance


class TestPathCompliance:
    """PathCompliance.assert_safe_path() のテスト"""

    def test_valid_path_within_project(self, tmp_path):
        """プロジェクト内の有効なパス"""
        target = tmp_path / "material" / "output"
        # エラーが発生しなければOK
        PathCompliance.assert_safe_path(target, tmp_path)

    def test_valid_nested_path(self, tmp_path):
        """深くネストした有効なパス"""
        target = tmp_path / "material" / "30days-curriculum" / "day01"
        PathCompliance.assert_safe_path(target, tmp_path)

    def test_valid_path_at_root(self, tmp_path):
        """ルート直下のパス"""
        target = tmp_path / "output"
        PathCompliance.assert_safe_path(target, tmp_path)

    def test_forbidden_home_in_suffix(self, tmp_path):
        """suffix に /home/ が含まれる場合"""
        # target_str が root_str で始まり、suffix に /home/ が含まれる
        target = tmp_path / "home" / "user" / "output"
        with pytest.raises(ValueError, match="CRITICAL SAFETY VIOLATION"):
            PathCompliance.assert_safe_path(target, tmp_path)

    def test_forbidden_users_in_suffix(self, tmp_path):
        """suffix に /Users/ が含まれる場合"""
        target = tmp_path / "Users" / "someone" / "output"
        with pytest.raises(ValueError, match="CRITICAL SAFETY VIOLATION"):
            PathCompliance.assert_safe_path(target, tmp_path)

    def test_forbidden_var_in_suffix(self, tmp_path):
        """suffix に /var/ が含まれる場合"""
        target = tmp_path / "var" / "log" / "output"
        with pytest.raises(ValueError, match="CRITICAL SAFETY VIOLATION"):
            PathCompliance.assert_safe_path(target, tmp_path)

    def test_forbidden_etc_in_suffix(self, tmp_path):
        """suffix に /etc/ が含まれる場合"""
        target = tmp_path / "etc" / "config" / "output"
        with pytest.raises(ValueError, match="CRITICAL SAFETY VIOLATION"):
            PathCompliance.assert_safe_path(target, tmp_path)

    def test_forbidden_usr_in_suffix(self, tmp_path):
        """suffix に /usr/ が含まれる場合"""
        target = tmp_path / "usr" / "local" / "output"
        with pytest.raises(ValueError, match="CRITICAL SAFETY VIOLATION"):
            PathCompliance.assert_safe_path(target, tmp_path)

    def test_path_not_starting_with_root(self, tmp_path):
        """ルートで始まらないパスは forbidden_roots チェックをスキップ"""
        # tmp_path とは関係ないパス
        other_path = Path("/some/other/path")
        target = Path("/completely/different/path")
        # target_str.startswith(root_str) が False なので
        # forbidden_roots チェックは実行されない
        # このテストは ValueError を発生させない
        PathCompliance.assert_safe_path(target, other_path)

    def test_same_path_as_root(self, tmp_path):
        """ルートと同じパス"""
        PathCompliance.assert_safe_path(tmp_path, tmp_path)

    def test_path_with_similar_name_but_safe(self, tmp_path):
        """似た名前だが安全なパス（例：homework）"""
        # "home" が含まれるが "/home/" ではない
        target = tmp_path / "homework" / "project"
        # "/home/" としてマッチしないので安全
        PathCompliance.assert_safe_path(target, tmp_path)

    def test_path_with_username_but_safe(self, tmp_path):
        """ユーザー名っぽいが安全なパス"""
        # "users" が含まれるが "/Users/" ではない
        target = tmp_path / "users_data" / "output"
        # "/Users/" としてマッチしないので安全
        PathCompliance.assert_safe_path(target, tmp_path)

    def test_error_message_contains_path_info(self, tmp_path):
        """エラーメッセージにパス情報が含まれる"""
        target = tmp_path / "home" / "leaked" / "path"
        with pytest.raises(ValueError) as exc_info:
            PathCompliance.assert_safe_path(target, tmp_path)
        error_message = str(exc_info.value)
        assert "Target:" in error_message
        assert "/home/" in error_message
        assert "forbidden pattern" in error_message


class TestPathComplianceEdgeCases:
    """エッジケースのテスト"""

    def test_deeply_nested_forbidden_path(self, tmp_path):
        """深くネストした禁止パス"""
        target = tmp_path / "a" / "b" / "c" / "home" / "user"
        with pytest.raises(ValueError, match="CRITICAL SAFETY VIOLATION"):
            PathCompliance.assert_safe_path(target, tmp_path)

    def test_multiple_forbidden_patterns(self, tmp_path):
        """複数の禁止パターン（最初のものでエラー）"""
        # 実際には最初のパターンでエラーになる
        target = tmp_path / "home" / "Users" / "output"
        with pytest.raises(ValueError):
            PathCompliance.assert_safe_path(target, tmp_path)

    def test_relative_path_resolution(self, tmp_path):
        """相対パスの解決"""
        # 相対パスは resolve() される
        target = tmp_path / "material" / ".." / "output"
        # 解決後は tmp_path/output になる
        PathCompliance.assert_safe_path(target, tmp_path)

    def test_symlink_like_path(self, tmp_path):
        """シンボリックリンクのようなパス構造"""
        # .. を含むパス
        target = tmp_path / "dir1" / ".." / "dir2" / "output"
        PathCompliance.assert_safe_path(target, tmp_path)
