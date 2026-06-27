#!/usr/bin/env bash
set -euo pipefail

# EN: Build the paper-compatible Docker image.
# CN: 构建论文兼容的 Docker 镜像。
docker compose -f docker/netconfeval-paper/compose.yaml build

# EN: Run the Level 0 smoke baseline.
# CN: 运行 Level 0 smoke 基线。
docker compose -f docker/netconfeval-paper/compose.yaml run --rm netconfeval-paper \
  bash docker/netconfeval-paper/scripts/run_smoke.sh
