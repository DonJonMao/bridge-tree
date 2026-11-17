
# ===================== Configuration ===================== #

BASE_MODEL="Qwen/Qwen2.5-7B-Instruct"



MAX_LORA_RANK=64

PORT=8003
# ========================================================= #

# Cleanup handler
cleanup() {
  echo ""
  echo "🧹 Cleaning up retriever and vLLM..."
  ps aux | grep '' | grep 'vllm serve' | awk '{print $2}' | xargs kill
  wait
  echo "✅ Cleanup done."
}

# Trap Ctrl+C
trap 'echo ""; echo "❌ Interrupted!"; cleanup; exit 1' SIGINT SIGTERM
export VLLM_USE_V1=0
export VLLM_NO_USAGE_STATS=1

echo "🚀 Launching vLLM model in foreground on all GPUs..."
CMD=" CUDA_VISIBLE_DEVICES=0 python serve_vllm.py \
  --model \"$BASE_MODEL\" \
  --port $PORT"

if [ -n "$LORA_PATH" ]; then
  CMD="$CMD --lora-modules finetune=$LORA_PATH --max-lora-rank $MAX_LORA_RANK"
fi

eval $CMD

cleanup
exit 0
