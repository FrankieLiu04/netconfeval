# AGENTS.md

## Project Shape

This repository is an independent NetConfEval paper reproduction workspace.

- Keep upstream NetConfEval code outside git at `research/netconfeval/`.
- Keep paper-compatible legacy dependencies isolated in `docker/netconfeval-paper`.
- Keep the Python runner under `research/netconfeval_repro`.
- Do not add FYP CML/MCP agent code here.

## Verification

```bash
uv run python -m pytest tests/ -v
```

Docker checks require a compliant container runtime:

```bash
docker compose -f docker/netconfeval-paper/compose.yaml build
docker compose -f docker/netconfeval-paper/compose.yaml run --rm netconfeval-paper \
  bash docker/netconfeval-paper/scripts/run_smoke.sh
```

## Safety

- Do not commit API keys, `.env`, or raw credential-bearing logs.
- Keep large upstream snapshots and generated local outputs out of git.
- Public-facing summaries should avoid personal, university account, or company
  network details.
