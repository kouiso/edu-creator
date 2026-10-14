#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

LOGFILE="$SCRIPT_DIR/batch_progress.log"
FAILED_CHAPTERS="$SCRIPT_DIR/failed_chapters.txt"

echo "=== Batch Generation Started: $(date) ===" | tee -a "$LOGFILE"
> "$FAILED_CHAPTERS"

for CHAPTER in {2..30}; do
    echo "" | tee -a "$LOGFILE"
    echo "--- Processing Chapter $CHAPTER ($(date)) ---" | tee -a "$LOGFILE"

    # ステップ1: Markdown生成
    if python main.py --config ../edu-config.yaml --chapters "$CHAPTER" 2>&1 | tee -a "$LOGFILE"; then
        echo "✅ Chapter $CHAPTER: Markdown generated" | tee -a "$LOGFILE"
    else
        echo "❌ Chapter $CHAPTER: Generation FAILED" | tee -a "$LOGFILE"
        echo "$CHAPTER" >> "$FAILED_CHAPTERS"
        continue
    fi

    # ステップ2: 品質レポート確認
    QUALITY_REPORT="$PROJECT_ROOT/material/30days-curriculum/day$(printf %02d $CHAPTER)_*_quality_report.txt"
    if ls $QUALITY_REPORT 1> /dev/null 2>&1; then
        if grep -q "PASS" $QUALITY_REPORT; then
            echo "✅ Chapter $CHAPTER: Quality PASSED" | tee -a "$LOGFILE"
        else
            echo "⚠️  Chapter $CHAPTER: Quality FAILED (continuing)" | tee -a "$LOGFILE"
            cat $QUALITY_REPORT | tee -a "$LOGFILE"
        fi
    else
        echo "⚠️  Chapter $CHAPTER: No quality report found" | tee -a "$LOGFILE"
    fi

    # ステップ3: PDF生成
    cd $PROJECT_ROOT
    if bash script/generate_pdf.sh all 2>&1 | tee -a "$LOGFILE"; then
        echo "✅ Chapter $CHAPTER: PDF generated" | tee -a "$LOGFILE"
    else
        echo "⚠️  Chapter $CHAPTER: PDF generation failed" | tee -a "$LOGFILE"
    fi
    cd $SCRIPT_DIR

    # ステップ4: レート制限回避（10秒待機）
    echo "   Cooling down for 10 seconds..." | tee -a "$LOGFILE"
    sleep 10
done

echo "" | tee -a "$LOGFILE"
echo "=== Batch Generation Completed: $(date) ===" | tee -a "$LOGFILE"

if [ -s "$FAILED_CHAPTERS" ]; then
    echo "⚠️  Failed chapters:" | tee -a "$LOGFILE"
    cat "$FAILED_CHAPTERS" | tee -a "$LOGFILE"
else
    echo "✅ All 29 chapters generated successfully!" | tee -a "$LOGFILE"
fi
