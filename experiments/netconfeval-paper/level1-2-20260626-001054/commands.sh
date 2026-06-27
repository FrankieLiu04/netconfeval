#!/usr/bin/env bash
set -euo pipefail

RUN_ID="level1-2-20260626-001054"

# EN: Level 1: Step 1 faithful translation at smoke scale.
# CN: Level 1：以 smoke 规模运行 Step 1 faithful translation。
# EN: Set STEP1_TRANSLATION_RESULTS_DIR with `-e` to avoid the upstream default path.
# CN: 用 `-e` 传入 STEP1_TRANSLATION_RESULTS_DIR 可避免写到上游默认路径。
docker compose -f docker/netconfeval-paper/compose.yaml run --rm netconfeval-paper \
  bash docker/netconfeval-paper/scripts/run_step1_translation.sh \
  --max-chunks-per-batch 1

# EN: Level 2: one reachability sample for the function-call probe.
# CN: Level 2：函数调用 probe 使用一个 reachability 样本。
docker compose -f docker/netconfeval-paper/compose.yaml run --rm \
  -e STEP1_FUNCTION_RESULTS_PATH="/workspace/experiments/netconfeval-paper/${RUN_ID}/level2_function_call_results" \
  netconfeval-paper \
  bash docker/netconfeval-paper/scripts/run_step1_function_call.sh
