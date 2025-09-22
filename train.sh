#!/bin/sh
set -eu

# Assumes you have created the conda environment `econ-ie` with:
#   conda env create -f environment.yml
# And activated it with:
#   conda activate econ-ie
#
# Pick a batch size that fits your GPU memory; e.g., RTX 3090 24GB fits --batch 32

# -------------------------
# Configuration (overridable via env; arg1 can override batch size)
# -------------------------
BATCH_SIZE="${BATCH_SIZE:-${1:-32}}"
EPOCHS="${EPOCHS:-5}"
MODEL_NAME="${MODEL_NAME:-worldbank/econberta-fs}"

TRAIN_FILE="${TRAIN_FILE:-data/econ_ie/train.conll}"
VAL_FILE="${VAL_FILE:-data/econ_ie/dev.conll}"
TEST_FILE="${TEST_FILE:-data/econ_ie/test.conll}"
OUTPUT_DIR="${OUTPUT_DIR:-models/econberta-fs-econ-ie-ner-tuned}"

# -------------------------
# Helpers
# -------------------------
run() {
  echo
  echo "==> $*"
  "$@"
}

# -------------------------
# Checks
# -------------------------
[ -f "$TRAIN_FILE" ] || { echo "Error: TRAIN_FILE not found: $TRAIN_FILE" >&2; exit 1; }
[ -f "$VAL_FILE" ]   || { echo "Error: VAL_FILE not found: $VAL_FILE" >&2; exit 1; }
[ -f "$TEST_FILE" ]  || { echo "Error: TEST_FILE not found: $TEST_FILE" >&2; exit 1; }
[ -f "tools/trainer.py" ] || { echo "Error: tools/trainer.py not found" >&2; exit 1; }
mkdir -p "$OUTPUT_DIR"

echo "Config: batch=$BATCH_SIZE epochs=$EPOCHS model='$MODEL_NAME'"
echo "Data: train='$TRAIN_FILE' dev='$VAL_FILE' test='$TEST_FILE'"
echo "Output: '$OUTPUT_DIR'"

# -------------------------
# Train
# -------------------------
run python tools/trainer.py \
  --model_name "$MODEL_NAME" \
  --train_file "$TRAIN_FILE" \
  --validation_file "$VAL_FILE" \
  --test_file "$TEST_FILE" \
  --output_dir "$OUTPUT_DIR" \
  --epochs "$EPOCHS" \
  --batch "$BATCH_SIZE"

echo
echo "Done. Model saved to: $OUTPUT_DIR"