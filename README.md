# NetConfEval Paper Reproduction

Independent reproduction workspace for selected NetConfEval paper experiments.

This repository contains wrapper code, Docker scripts, small-sample experiment
summaries, and result artifacts used to reproduce parts of:

- NetConfEval: https://github.com/RedHatResearch/conext24-NetConfEval
- Paper DOI: https://doi.org/10.1145/3656296

The upstream NetConfEval repository is not vendored here. The Docker helper
clones the upstream project at a pinned commit during execution:

```text
24edc15b6f94e1b5805ae904cc05676eca2f02fe
```

## Scope

- Step 1 faithful formal-spec translation runner.
- Step 1 function-call probe through the upstream scripts.
- Step 2 code-generation probe through the upstream scripts.
- Small DeepSeek/OpenAI-compatible reproduction results.
- A paper-compatible Docker environment isolated from the FYP agent project.

Step 3 Kathara/FRR simulation is intentionally out of scope for this snapshot.

## Layout

```text
docker/netconfeval-paper/      # paper-compatible Docker environment
research/netconfeval_repro/    # maintainable reproduction runner
research/legacy/               # early smoke reproduction archive
experiments/netconfeval-paper/ # selected summaries and result artifacts
tests/research/                # lightweight runner tests
```

## Local Python Checks

```bash
uv sync --extra dev
uv run python -m pytest tests/ -v
```

The lightweight tests skip upstream-dependent cases if the upstream NetConfEval
snapshot has not been checked out.

## Docker Reproduction

The Docker path is documented in:

```text
docker/netconfeval-paper/README.md
```

Typical smoke run:

```bash
docker compose -f docker/netconfeval-paper/compose.yaml build
docker compose -f docker/netconfeval-paper/compose.yaml run --rm netconfeval-paper \
  bash docker/netconfeval-paper/scripts/run_smoke.sh
```

Provide either `OPENAI_API_KEY` or `DEEPSEEK_API_KEY` through your local
environment or `.env`. Do not commit real credentials.

## Compliance Note

Docker Desktop may require a paid license in some company-managed environments.
Use a compliant local machine, Linux VM, lab server, cloud VM, or approved
container runtime.
