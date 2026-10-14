#!/usr/bin/env python3
"""
技術スタック検証スクリプト

禁止技術（MUI等）の使用と、必須技術（shadcn/ui等）の不使用を検出します。
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# =============================================================================
# 禁止パターン（MUI等）
# =============================================================================
FORBIDDEN_PATTERNS = [
    # MUI インポート
    (r'@mui/material', 'MUIは禁止です。shadcn/uiコンポーネントを使用してください。'),
    (r'@mui/icons-material', 'MUIアイコンは禁止です。lucide-reactを使用してください。'),
    (r'@mui/system', 'MUI systemは禁止です。Tailwind CSSを使用してください。'),
    (r'@emotion/react', 'emotionは禁止です。Tailwind CSSを使用してください。'),
    (r'@emotion/styled', 'emotion styledは禁止です。Tailwind CSSを使用してください。'),

    # MUI コンポーネント使用
    (r'import\s*\{[^}]*\}\s*from\s*[\'"]@mui', 'MUIからのインポートは禁止です。'),
    (r'<Box\s', 'MUIの<Box>は禁止です。<div className="...">を使用してください。'),
    (r'<Typography\s', 'MUIの<Typography>は禁止です。<p>/<h1>-<h6>を使用してください。'),
    (r'<TextField\s', 'MUIの<TextField>は禁止です。shadcn/uiのInputを使用してください。'),
    (r'<MuiButton', 'MUIのButtonは禁止です。shadcn/uiのButtonを使用してください。'),

    # MUI sx prop
    (r'sx=\{\{', 'MUIのsx propは禁止です。Tailwind CSSクラスを使用してください。'),

    # コード分割パターン
    (r'パート\d+/\d+', 'コードの「パートn/m」分割は禁止です。機能単位で分割してください。'),
    (r'（パート\d+）', 'コードの「（パートn）」分割は禁止です。機能単位で分割してください。'),
    (r'（前半）', '「（前半）」分割は禁止です。機能単位で分割してください。'),
    (r'（後半）', '「（後半）」分割は禁止です。機能単位で分割してください。'),
    (r'// \.\.\.残り', '「// ...残り」省略は禁止です。完全なコードを書いてください。'),
    (r'// 省略', '「// 省略」は禁止です。完全なコードを書いてください。'),
    (r'// 以下略', '「// 以下略」は禁止です。完全なコードを書いてください。'),
]

# =============================================================================
# フォーム実装チェック（useState個別管理の検出）
# =============================================================================
FORM_WARNING_PATTERNS = [
    (r'const\s*\[\w+,\s*set\w+\]\s*=\s*useState\([\'"]',
     '⚠️  useStateでフォーム値を管理しています。react-hook-formの使用を検討してください。'),
]


def check_file(filepath: Path) -> Tuple[int, int, List[Tuple[int, str, str]]]:
    """
    ファイルをチェックして禁止パターンの出現箇所を返す。

    Returns:
        (エラー数, 警告数, [(行番号, パターン, メッセージ), ...])
    """
    errors: List[Tuple[int, str, str]] = []
    warnings: List[Tuple[int, str, str]] = []

    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        print(f"❌ ファイル読込エラー: {filepath}")
        print(f"   {e}")
        return 0, 0, []

    lines = content.split('\n')
    in_code_block = False

    for line_num, line in enumerate(lines, 1):
        # コードブロックの開始/終了を追跡
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            continue

        # 禁止パターンチェック（コードブロック内外両方）
        for pattern, message in FORBIDDEN_PATTERNS:
            if re.search(pattern, line):
                errors.append((line_num, pattern, f"❌ {message}"))

        # フォーム警告チェック（コードブロック内のみ）
        if in_code_block:
            for pattern, message in FORM_WARNING_PATTERNS:
                if re.search(pattern, line):
                    warnings.append((line_num, pattern, message))

    return len(errors), len(warnings), errors + warnings


def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("使用法: python check_tech_stack.py <directory_or_file>")
        print("例: python check_tech_stack.py material/30days-curriculum/")
        sys.exit(1)

    target_path = Path(sys.argv[1])

    if not target_path.exists():
        print(f"❌ パスが見つかりません: {target_path}")
        sys.exit(1)

    # Markdownファイル取得
    if target_path.is_dir():
        md_files = sorted(target_path.glob('day*.md'))
    else:
        md_files = [target_path]

    if not md_files:
        print(f"⚠️  Markdownファイルが見つかりません: {target_path}")
        sys.exit(0)

    print("=" * 70)
    print("🔧 技術スタック検証スクリプト")
    print("   - MUI禁止、shadcn/ui + Tailwind CSS必須")
    print("   - react-hook-form + zod推奨")
    print("=" * 70)
    print()

    total_errors = 0
    total_warnings = 0
    files_with_issues = 0

    for md_file in md_files:
        error_count, warning_count, issues = check_file(md_file)
        total_errors += error_count
        total_warnings += warning_count

        if issues:
            files_with_issues += 1
            status = "❌" if error_count > 0 else "⚠️"
            print(f"{status} {md_file.name}: {error_count}エラー, {warning_count}警告")
            for line_num, pattern, message in issues:
                print(f"   L{line_num}: {message}")
            print()

    print("=" * 70)
    if total_errors == 0 and total_warnings == 0:
        print("✅ 技術スタック違反は見つかりませんでした！")
        print("=" * 70)
        sys.exit(0)
    elif total_errors == 0:
        print(f"⚠️  {files_with_issues}ファイルに {total_warnings}個の警告があります")
        print("   （警告は改善推奨ですが、必須ではありません）")
        print("=" * 70)
        sys.exit(0)  # 警告のみはPASS
    else:
        print(f"❌ {files_with_issues}ファイルに {total_errors}個のエラーが見つかりました")
        print("   MUI使用やコード分割は禁止です。修正してください。")
        print("=" * 70)
        sys.exit(1)


if __name__ == '__main__':
    main()
