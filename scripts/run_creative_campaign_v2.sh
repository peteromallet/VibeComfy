#!/bin/zsh
# Creative scenario factory drive.
# Goal: Bank 20 creative (LLM-proposed) scenarios that PASS (oracle-verified).
set -e

CAMPAIGN_ROOT="out/demo-candidate-factory/20260723-001"
MAX_CREATIVE_PASS=20

# Diverse modern templates spanning modalities, complexities, and models
WORKFLOWS=(
    "image/basic_image_upscale"
    "image/z_image"
    "image/z_image_img2img"
    "image/qwen_image_2512"
    "image/flux2_klein_4b_t2i"
    "image/flux2_klein_9b_t2i"
    "video/wan_t2v"
    "video/wan_i2v"
    "video/ltx2_3_lightricks_two_stage"
    "audio/qwen3_tts_voice_clone"
    "audio/ace_step_1_5_t2a_song"
    "edit/flux2_klein_4b_image_edit_base"
)

mkdir -p "$CAMPAIGN_ROOT/logs"

echo "Starting creative campaign to bank $MAX_CREATIVE_PASS creative PASS scenarios"
echo "Campaign root: $CAMPAIGN_ROOT"
echo "Starting at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

TOTAL_ATTEMPTS=0

while true; do
    # Count current creative successful scenarios (ALT + accepted)
    CURRENT_CREATIVE_PASS=0
    if [[ -f "$CAMPAIGN_ROOT/events.jsonl" ]]; then
        # Extract all creative events with their verdicts
        creative_pass=$(grep '"source": "creative"' "$CAMPAIGN_ROOT/events.jsonl" 2>/dev/null | grep -E '"verdict": "(alternative_repair|accepted)"' | wc -l | tr -d ' ')
        CURRENT_CREATIVE_PASS=${creative_pass:-0}
    fi

    # Extract detailed counts for display
    creative_alt=0
    creative_acc=0
    if [[ -f "$CAMPAIGN_ROOT/events.jsonl" ]]; then
        creative_acc=$(grep '"source": "creative"' "$CAMPAIGN_ROOT/events.jsonl" 2>/dev/null | grep -c '"verdict": "accepted"' || true)
        creative_alt=$(grep '"source": "creative"' "$CAMPAIGN_ROOT/events.jsonl" 2>/dev/null | grep -c '"verdict": "alternative_repair"' || true)
    fi

    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Creative PASS: $CURRENT_CREATIVE_PASS/$MAX_CREATIVE_PASS (ALT:$creative_alt + ACC:$creative_acc) | Total attempts: $TOTAL_ATTEMPTS"

    if [[ $CURRENT_CREATIVE_PASS -ge $MAX_CREATIVE_PASS ]]; then
        echo "Achieved $CURRENT_CREATIVE_PASS creative PASS scenarios. Stopping."
        break
    fi

    # Pick a workflow (round-robin through the list for diversity)
    WORKFLOW="${WORKFLOWS[$((TOTAL_ATTEMPTS % ${#WORKFLOWS[@]}))]}"

    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Attempt $((TOTAL_ATTEMPTS + 1)): $WORKFLOW"

    # Run creative case
    if python -m vibecomfy.demo_factory.cli run-creative \
        --ready "$WORKFLOW" \
        --campaign "$CAMPAIGN_ROOT" \
        --tag "demo-factory"; then
        echo "  -> Completed successfully"
    else
        echo "  -> Failed with exit code $?"
    fi

    TOTAL_ATTEMPTS=$((TOTAL_ATTEMPTS + 1))

    # Safety limit
    if [[ $TOTAL_ATTEMPTS -ge 200 ]]; then
        echo "Reached 200 total attempts. Stopping for safety."
        break
    fi

    # Brief pause
    sleep 2
done

echo ""
echo "Campaign complete!"
echo "Total attempts: $TOTAL_ATTEMPTS"
echo "Final creative PASS count: $CURRENT_CREATIVE_PASS"
echo "Ended at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
