#!/bin/bash
#
# 教材品質チェック一括実行スクリプト（edu-creator 配下版）
# 使用法: ./edu-creator/script/check_quality.sh material/30days-curriculum/

set -e

if [ -z "$1" ]; then
    echo "使用法: $0 <directory>"
    echo "例: $0 material/30days-curriculum/"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TARGET_DIR="$1"

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║           📋 教材品質チェック（3段階）                              ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# 1. 禁止ワードチェック
echo "────────────────────────────────────────────────────────────────────"
echo "Step 1: 禁止ワード検出（AIの手抜き検出）"
echo "────────────────────────────────────────────────────────────────────"
python3 "${SCRIPT_DIR}/check_no_skip.py" "$TARGET_DIR" || STEP1_FAIL=1
echo ""

# 1.5. 技術スタックチェック（MUI禁止、shadcn/ui必須）
echo "────────────────────────────────────────────────────────────────────"
echo "Step 1.5: 技術スタック検証（MUI禁止、shadcn/ui必須）"
echo "────────────────────────────────────────────────────────────────────"
python3 "${SCRIPT_DIR}/check_tech_stack.py" "$TARGET_DIR" || STEP1_5_FAIL=1
echo ""

# 2. ステップ長チェック
echo "────────────────────────────────────────────────────────────────────"
echo "Step 2: ステップ長チェック（コード25行以下、段落3文以下）"
echo "────────────────────────────────────────────────────────────────────"
python3 "${SCRIPT_DIR}/check_step_length.py" "$TARGET_DIR" || STEP2_FAIL=1
echo ""

# 3. ビジュアル化チェック
echo "────────────────────────────────────────────────────────────────────"
echo "Step 3: ビジュアル化要素チェック（表4+、図1+）"
echo "────────────────────────────────────────────────────────────────────"
python3 "${SCRIPT_DIR}/check_visualization.py" "$TARGET_DIR" || STEP3_FAIL=1
echo ""

# 結果サマリー
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                       チェック結果サマリー                          ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

if [ -z "$STEP1_FAIL" ] && [ -z "$STEP1_5_FAIL" ] && [ -z "$STEP2_FAIL" ] && [ -z "$STEP3_FAIL" ]; then
    echo "🎉 全てのチェックに合格しました！"
    echo ""
    exit 0
else
    echo "⚠️  改善が必要な項目があります："
    [ -n "$STEP1_FAIL" ] && echo "   ❌ Step 1: 禁止ワードが見つかりました"
    [ -n "$STEP1_5_FAIL" ] && echo "   ❌ Step 1.5: 技術スタック違反（MUI使用等）があります"
    [ -n "$STEP2_FAIL" ] && echo "   ⚠️  Step 2: ステップの長さを調整してください"
    [ -n "$STEP3_FAIL" ] && echo "   📊 Step 3: ビジュアル化要素を追加してください"
    echo ""
    exit 1
fi
