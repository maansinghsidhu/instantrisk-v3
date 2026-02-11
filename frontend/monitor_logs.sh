#!/bin/bash

# InstantRisk V2 Log Monitor Script
# Tracks statistics every 5 minutes

OUT_LOG="/home/maani/.pm2/logs/ir2-api-out.log"
ERR_LOG="/home/maani/.pm2/logs/ir2-api-error.log"
REPORT="/home/maani/instantrisk-v2/log_monitor_report.txt"
STATE_FILE="/home/maani/instantrisk-v2/mobile/monitor_state.txt"

# Initialize or read previous line counts
if [ -f "$STATE_FILE" ]; then
    source "$STATE_FILE"
else
    PREV_OUT_LINES=148227
    PREV_ERR_LINES=65965
    TOTAL_REQUESTS=0
    TOTAL_ERRORS=0
    TOTAL_ANALYSIS=0
    TOTAL_SANCTIONS=0
    TOTAL_UPLOADS=0
    TOTAL_OCR=0
fi

# Get current line counts
CURR_OUT_LINES=$(wc -l < "$OUT_LOG" 2>/dev/null || echo 0)
CURR_ERR_LINES=$(wc -l < "$ERR_LOG" 2>/dev/null || echo 0)

# Calculate new lines
NEW_OUT=$((CURR_OUT_LINES - PREV_OUT_LINES))
NEW_ERR=$((CURR_ERR_LINES - PREV_ERR_LINES))

if [ $NEW_OUT -lt 0 ]; then NEW_OUT=0; fi
if [ $NEW_ERR -lt 0 ]; then NEW_ERR=0; fi

# Get statistics from new lines in out.log
if [ $NEW_OUT -gt 0 ]; then
    REQUESTS=$(tail -n $NEW_OUT "$OUT_LOG" | grep -c "HTTP/1.1" 2>/dev/null) || REQUESTS=0
    ANALYSIS=$(tail -n $NEW_OUT "$OUT_LOG" | grep -ciE "process-async|analyze|autogen" 2>/dev/null) || ANALYSIS=0
    SANCTIONS=$(tail -n $NEW_OUT "$OUT_LOG" | grep -ci "sanctions" 2>/dev/null) || SANCTIONS=0
    UPLOADS=$(tail -n $NEW_OUT "$OUT_LOG" | grep -ci "upload" 2>/dev/null) || UPLOADS=0
    OCR=$(tail -n $NEW_OUT "$OUT_LOG" | grep -ciE "ocr|rapidocr" 2>/dev/null) || OCR=0
else
    REQUESTS=0
    ANALYSIS=0
    SANCTIONS=0
    UPLOADS=0
    OCR=0
fi

# Count errors from error.log
if [ $NEW_ERR -gt 0 ]; then
    ERRORS=$(tail -n $NEW_ERR "$ERR_LOG" | grep -ciE "error|exception|traceback" 2>/dev/null) || ERRORS=0
else
    ERRORS=0
fi

# Ensure all values are numeric
REQUESTS=${REQUESTS:-0}
ANALYSIS=${ANALYSIS:-0}
SANCTIONS=${SANCTIONS:-0}
UPLOADS=${UPLOADS:-0}
OCR=${OCR:-0}
ERRORS=${ERRORS:-0}

# Update running totals
TOTAL_REQUESTS=$((TOTAL_REQUESTS + REQUESTS))
TOTAL_ERRORS=$((TOTAL_ERRORS + ERRORS))
TOTAL_ANALYSIS=$((TOTAL_ANALYSIS + ANALYSIS))
TOTAL_SANCTIONS=$((TOTAL_SANCTIONS + SANCTIONS))
TOTAL_UPLOADS=$((TOTAL_UPLOADS + UPLOADS))
TOTAL_OCR=$((TOTAL_OCR + OCR))

# Write report entry
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
cat >> "$REPORT" << ENTRY

[$TIMESTAMP] ------------------------------------------------
New lines: out=$NEW_OUT, err=$NEW_ERR
  HTTP Requests:    $REQUESTS (total: $TOTAL_REQUESTS)
  Errors:           $ERRORS (total: $TOTAL_ERRORS)
  Analysis Jobs:    $ANALYSIS (total: $TOTAL_ANALYSIS)
  Sanctions Checks: $SANCTIONS (total: $TOTAL_SANCTIONS)
  Document Uploads: $UPLOADS (total: $TOTAL_UPLOADS)
  OCR Operations:   $OCR (total: $TOTAL_OCR)
ENTRY

# Save state
cat > "$STATE_FILE" << STATE
PREV_OUT_LINES=$CURR_OUT_LINES
PREV_ERR_LINES=$CURR_ERR_LINES
TOTAL_REQUESTS=$TOTAL_REQUESTS
TOTAL_ERRORS=$TOTAL_ERRORS
TOTAL_ANALYSIS=$TOTAL_ANALYSIS
TOTAL_SANCTIONS=$TOTAL_SANCTIONS
TOTAL_UPLOADS=$TOTAL_UPLOADS
TOTAL_OCR=$TOTAL_OCR
STATE

echo "[$TIMESTAMP] Check complete - $NEW_OUT new out lines, $NEW_ERR new err lines"
