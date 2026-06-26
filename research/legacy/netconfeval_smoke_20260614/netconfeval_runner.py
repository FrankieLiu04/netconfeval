"""Minimal NetConfEval Step 1 runner — uses openai directly, no langchain.

Reproduces the benchmark logic from:
  netconfeval/step_1_formal_spec_translation.py
  netconfeval/step_1_formal_spec_conflict_detection.py

Usage (from repo root):
  OPENAI_API_KEY=... OPENAI_BASE_URL=https://api.deepseek.com \
  uv run python research/netconfeval_runner.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from deepdiff import DeepDiff
from openai import OpenAI

# ── Config ───────────────────────────────────────────────────────────────────
MODEL = os.getenv("NETCONFEVAL_MODEL", "deepseek-v4-flash")
N_RUNS = int(os.getenv("NETCONFEVAL_N_RUNS", "5"))
RESULTS_DIR = Path("research/netconfeval/results_spec_translation")
ASSETS_DIR = Path("research/netconfeval/assets")

# NetConfEval prompts (extracted from their source)
SYSTEM_PROMPT = """Your task is to transform the network requirements into a formal specification.
You only reply in JSON, no natural language.
If the response is successful, reply with: {"status": "OK", "result": "<RESULT>"}
If the response fails, reply with: {"status": "ERROR", "reason": "<YOUR_REASON>"}."""

FUNCTION_PROMPT = """The network requirements are:

a. Reachability
Given location l1 and prefix p1, reachability from l1 to p1 means that l1 can send packets to p1 directly or through other locations.

b. Waypoint
Given location l1 and destination prefix p1, waypoint means that if l1 wants to reach p1, the traffic path should include a list of locations.

c. Load Balancing
Given location l1 and destination prefix p1, load balancing means if l1 wants to reach p1, the traffic path should be load-balanced across a certain number of paths.

The formal specification format is JSON:
{
  "reachability": {"<source>": ["<prefix1>", "<prefix2>", ...]},
  "waypoint": {"<source>": {"<prefix>": ["<wp1>", "<wp2>", ...]}},
  "loadbalancing": {"<source>": {"<prefix>": <num_paths>}}
}

Translate the following requirements into formal specification JSON only."""

ASK_FOR_RESULT = "Give the result in JSON only, no additional text."

# CSV column names in the NetConfEval dataset
# From assets/step_1_policies.csv: source,prefix,policy_type[,waypoint|num]


def load_csv(csv_path: str, policy_types: set[str]) -> list[dict]:
    """Load the step_1_policies.csv using NetConfEval's exact parsing logic."""
    filtered_data = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key_type = row["type"].replace("PolicyType.", "").replace("Simple", "").lower()
            if key_type not in policy_types:
                continue
            if key_type == "loadbalancing":
                filtered_row = {
                    "policy_type": key_type,
                    "source": row["Sources"],
                    "prefix": row["subnet"],
                    "waypoint": "",
                    "num": int(row["specifics"]),
                }
                filtered_data.append(filtered_row)
            elif row["Status"] == "PolicyStatus.HOLDS" and row["Sources"] != row["specifics"]:
                filtered_row = {
                    "policy_type": key_type,
                    "source": row["Sources"],
                    "prefix": row["subnet"],
                    "waypoint": row["specifics"] if key_type == "waypoint" else "",
                    "num": 2,
                }
                filtered_data.append(filtered_row)
    return filtered_data


def pick_sample(
    n: int, requirements: list[dict], iteration: int, policy_types: set[str]
) -> list[dict]:
    """Mimics NetConfEval's pick_sample."""
    import math, random

    random.seed(5000 + iteration)
    shuffled = sorted(requirements, key=lambda k: random.random())

    if policy_types == {"reachability"}:
        return [x for x in shuffled if x["policy_type"] == "reachability"][:n]

    n_per = math.ceil(n / len(policy_types))
    waypoint_samples = [x for x in shuffled if x["policy_type"] == "waypoint"][:n_per]

    final: list[dict] = []
    for w in waypoint_samples:
        r_samples = [
            x
            for x in requirements
            if x["policy_type"] == "reachability"
            and x["source"] == w["source"]
            and x["prefix"] == w["prefix"]
        ]
        if r_samples:
            final.append(r_samples.pop())
        final.append(w)
        if "loadbalancing" in policy_types:
            lb_samples = [
                x
                for x in requirements
                if x["policy_type"] == "loadbalancing"
                and x["source"] == w["source"]
                and x["prefix"] == w["prefix"]
            ]
            if lb_samples:
                final.append(lb_samples.pop())
    return final[:n]


def build_prompt(sample: list[dict], policy_types: list[str]) -> str:
    """Convert a batch of policy rows into a human-language requirements string."""
    lines = []
    for item in sample:
        if item.get("policy_type") == "reachability":
            lines.append(f"{item['source']} can reach {item['prefix']}.")
        elif item.get("policy_type") == "waypoint":
            lines.append(
                f"Traffic from {item['source']} to {item['prefix']} "
                f"must pass through {item.get('waypoint', 'UNKNOWN')}."
            )
        elif item.get("policy_type") == "loadbalancing":
            lines.append(
                f"Traffic from {item['source']} to {item['prefix']} "
                f"should be load-balanced across {item.get('num', '2')} paths."
            )
    return " ".join(lines)


def transform_to_expected(sample: list[dict]) -> dict:
    """Build the expected formal spec from policy rows."""
    spec: dict[str, dict] = {"reachability": {}, "waypoint": {}, "loadbalancing": {}}
    for item in sample:
        ptype = item.get("policy_type", "")
        src = item["source"]
        prefix = item["prefix"]
        if ptype == "reachability":
            spec["reachability"].setdefault(src, []).append(prefix)
        elif ptype == "waypoint":
            spec["waypoint"].setdefault(src, {}).setdefault(prefix, []).append(
                item.get("waypoint", "")
            )
        elif ptype == "loadbalancing":
            spec["loadbalancing"].setdefault(src, {})[prefix] = int(
                item.get("num", "2")
            )
    # Remove empty sections
    return {k: v for k, v in spec.items() if v}


def call_llm(client: OpenAI, prompt: str) -> tuple[dict | None, int, int, float]:
    """Call the LLM and return (parsed_result, prompt_tokens, completion_tokens, cost_est)."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + "\n" + FUNCTION_PROMPT},
                {"role": "user", "content": prompt + "\n" + ASK_FOR_RESULT},
            ],
            temperature=0,
            max_tokens=4096,
            timeout=60.0,  # 60 second timeout per call
        )
        content = response.choices[0].message.content or ""
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0

        # Parse JSON from response
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content)
        # Extract the actual result field
        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        if isinstance(result, str):
            result = json.loads(result)

        # DeepSeek cost: ~$0.28/M input, ~$1.10/M output
        cost = (prompt_tokens * 0.28 + completion_tokens * 1.10) / 1_000_000
        return result, prompt_tokens, completion_tokens, cost
    except Exception as e:
        return None, 0, 0, 0.0


def run_benchmark(
    client: OpenAI,
    dataset: list[dict],
    policy_types: list[str],
    batch_sizes: list[int],
    n_runs: int,
) -> list[dict]:
    """Run the full benchmark and return result rows."""
    pset = set(policy_types)
    filtered = [r for r in dataset if r.get("policy_type") in pset]

    results: list[dict] = []
    for run_idx in range(n_runs):
        for batch_size in batch_sizes:
            n_required = batch_size * len(policy_types)
            if n_required > len(filtered):
                continue
            sample = pick_sample(n_required, filtered, run_idx, pset)
            if not sample:
                continue
            prompt = build_prompt(sample, policy_types)
            expected = transform_to_expected(sample)

            t0 = time.time()
            result, pt, ct, cost = call_llm(client, prompt)
            elapsed = time.time() - t0

            row = {
                "run": run_idx + 1,
                "batch_size": batch_size,
                "n_policy_types": len(policy_types),
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "cost_usd": round(cost, 6),
                "time_sec": round(elapsed, 2),
                "accuracy": 0,
                "diff": "",
            }

            if result is None:
                row["accuracy"] = 0
                row["diff"] = "LLM_ERROR"
            else:
                diff = DeepDiff(expected, result, ignore_order=True)
                row["diff"] = str(diff) if diff else "{}"
                row["accuracy"] = 1 if not diff else 0

            results.append(row)
            status = "OK" if row["accuracy"] else "FAIL"
            print(
                f"  [{status}] run={run_idx+1}/{n_runs} "
                f"batch={batch_size}*{len(policy_types)} "
                f"tokens={pt}+{ct} cost=${cost:.4f} "
                f"time={elapsed:.1f}s",
                flush=True,
            )

    return results


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL")
    if not api_key:
        print("ERROR: Set OPENAI_API_KEY or DEEPSEEK_API_KEY", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=base_url)

    # Locate the dataset
    dataset_path = ASSETS_DIR / "step_1_policies.csv"
    if not dataset_path.exists():
        print(f"ERROR: Dataset not found at {dataset_path}", file=sys.stderr)
        sys.exit(1)

    # Load all policy types at once
    dataset = load_csv(
        str(dataset_path),
        {"reachability", "waypoint", "loadbalancing"},
    )
    print(f"Loaded {len(dataset)} policy rows from {dataset_path}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results: list[dict] = []

    # ── Experiment 1: reachability only, varied batch sizes ──
    print("\n=== Step 1: Reachability only ===")
    res1 = run_benchmark(
        client, dataset, ["reachability"],
        batch_sizes=[1, 2, 5, 10, 20],
        n_runs=N_RUNS,
    )
    all_results.extend(res1)

    # ── Experiment 2: reachability + waypoint ──
    print("\n=== Step 1: Reachability + Waypoint ===")
    res2 = run_benchmark(
        client, dataset, ["reachability", "waypoint"],
        batch_sizes=[2, 4, 10, 20],
        n_runs=N_RUNS,
    )
    all_results.extend(res2)

    # ── Experiment 3: reachability + waypoint + loadbalancing ──
    print("\n=== Step 1: Reachability + Waypoint + LoadBalancing ===")
    res3 = run_benchmark(
        client, dataset, ["reachability", "waypoint", "loadbalancing"],
        batch_sizes=[3, 9, 33],
        n_runs=N_RUNS,
    )
    all_results.extend(res3)

    # ── Save results ──
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    csv_path = RESULTS_DIR / f"result-deepseek-v4-flash-step1-{timestamp}.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        if all_results:
            writer = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
            writer.writeheader()
            writer.writerows(all_results)

    # ── Summary ──
    total_acc = sum(r["accuracy"] for r in all_results)
    total_cost = sum(r["cost_usd"] for r in all_results)
    n = len(all_results)
    print(f"\n{'='*60}")
    print(f"Results saved to: {csv_path}")
    print(f"Total runs: {n}")
    print(f"Overall accuracy: {total_acc}/{n} = {total_acc/n*100:.1f}%")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
