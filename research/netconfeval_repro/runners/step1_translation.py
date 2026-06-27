# EN: NetConfEval Step 1 faithful translation runner.
# CN: NetConfEval Step 1 faithful translation runner。

from __future__ import annotations

import argparse
import csv
import os
import time
from pathlib import Path
from typing import Any

from sortedcontainers import SortedSet

from research.netconfeval_repro.adapters import ChatMessage, LLMAdapter, OpenAICompatibleAdapter
from research.netconfeval_repro.datasets.step1 import (
    chunk_list,
    convert_to_human_language,
    load_step1_dataset,
    pick_step1_sample,
    transform_sample_to_expected,
)
from research.netconfeval_repro.paths import DEFAULT_STEP1_POLICY_FILE, UPSTREAM_ROOT, ensure_upstream_on_path
from research.netconfeval_repro.scorers import parse_model_json, score_step1_result

ensure_upstream_on_path()


DEFAULT_MODEL = "deepseek-v4-flash"
POLICY_CONFIGS: tuple[tuple[tuple[str, ...], tuple[int, ...]], ...] = (
    (("reachability", "waypoint", "loadbalancing"), (1, 3, 11, 33)),
    (("reachability", "waypoint"), (1, 2, 5, 10, 25, 50)),
    (("reachability",), (1, 2, 5, 10, 20, 50, 100)),
)


def parse_args() -> argparse.Namespace:
    # EN: Parse command-line arguments.
    # CN: 解析命令行参数。
    parser = argparse.ArgumentParser(
        description="Run NetConfEval Step 1 translation with faithful sampling/scoring."
    )
    parser.add_argument("--model", default=os.getenv("NETCONFEVAL_MODEL", DEFAULT_MODEL))
    parser.add_argument("--n-runs", type=int, default=int(os.getenv("NETCONFEVAL_N_RUNS", "1")))
    parser.add_argument("--policy-file", type=Path, default=DEFAULT_STEP1_POLICY_FILE)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=UPSTREAM_ROOT / "results_spec_translation_faithful",
    )
    parser.add_argument(
        "--max-chunks-per-batch",
        type=int,
        default=None,
        help="Debug safety valve. Omit for faithful full chunk coverage.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=float(os.getenv("NETCONFEVAL_REQUEST_TIMEOUT", "90")),
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=int(os.getenv("NETCONFEVAL_MAX_TOKENS", "8192")),
    )
    return parser.parse_args()


def prompts_for(policy_types: SortedSet[str]) -> tuple[str, str, str]:
    # EN: Select the Step 1 prompt using original NetConfEval logic.
    # CN: 按原 NetConfEval 逻辑选择 Step 1 prompt。
    if "loadbalancing" in policy_types:
        from netconfeval.prompts.step_1_reachability_waypoint_load import (
            ASK_FOR_RESULT_PROMPT,
            FUNCTION_PROMPT,
            SETUP_PROMPT,
        )
    elif "waypoint" in policy_types:
        from netconfeval.prompts.step_1_reachability_waypoint import (
            ASK_FOR_RESULT_PROMPT,
            FUNCTION_PROMPT,
            SETUP_PROMPT,
        )
    else:
        from netconfeval.prompts.step_1_reachability import (
            ASK_FOR_RESULT_PROMPT,
            FUNCTION_PROMPT,
            SETUP_PROMPT,
        )
    return SETUP_PROMPT, FUNCTION_PROMPT, ASK_FOR_RESULT_PROMPT


def call_model(
    adapter: LLMAdapter,
    policy_types: SortedSet[str],
    human_language: list[str],
    timeout: float,
    max_tokens: int,
) -> tuple[dict[str, Any] | None, str, int, int, str]:
    # EN: Call the model and return result, error, token counts, and raw text.
    # CN: 调用模型，返回 result、错误、token 统计和原始文本。
    setup_prompt, function_prompt, ask_prompt = prompts_for(policy_types)
    try:
        response = adapter.complete_json(
            [
                ChatMessage(role="system", content=setup_prompt),
                ChatMessage(role="system", content=function_prompt),
                ChatMessage(role="user", content=" ".join(human_language)),
                ChatMessage(role="system", content=ask_prompt),
            ],
            timeout=timeout,
            max_tokens=max_tokens,
        )
        return (
            parse_model_json(response.content),
            "",
            response.prompt_tokens,
            response.completion_tokens,
            response.content,
        )
    except Exception as exc:
        # EN: This boundary covers remote LLM failures and malformed model JSON.
        # CN: 该边界覆盖远端 LLM 失败和模型 JSON 畸形。
        return None, f"{type(exc).__name__}: {exc}", 0, 0, ""


def build_empty_row(
    *,
    model_error: str,
    batch_size: int,
    n_policy_types: int,
    policy_types: SortedSet[str],
    max_n_requirements: int,
    iteration: int,
    chunk_index: int,
    elapsed_seconds: float,
    prompt_tokens: int,
    completion_tokens: int,
    raw_output: str,
) -> dict[str, Any]:
    # EN: Build stable fields for a Step 1 CSV row.
    # CN: 构建 Step 1 CSV row 的稳定字段。
    return {
        "model_error": model_error,
        "format_error": "",
        "batch_size": batch_size,
        "n_policy_types": n_policy_types,
        "policy_types": " ".join(policy_types),
        "max_n_requirements": max_n_requirements,
        "iteration": iteration,
        "chunk": chunk_index,
        "time": round(elapsed_seconds, 3),
        "total": 0,
        "success": 0,
        "fail": 0,
        "wrong": 0,
        "accuracy": 0,
        "strict_exact_match": 0,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_cost": 0,
        "diff": "",
        "raw_output": raw_output,
    }


def print_progress(row: dict[str, Any], n_runs: int, chunk_count: int) -> None:
    # EN: Print the progress line for one chunk.
    # CN: 打印单个 chunk 的进度行。
    status = "OK" if row["accuracy"] else "FAIL"
    print(
        f"[{status}] policies={row['policy_types']} "
        f"iter={row['iteration'] + 1}/{n_runs} batch={row['batch_size']} "
        f"chunk={row['chunk'] + 1}/{chunk_count} "
        f"acc={row['accuracy']} exact={row['strict_exact_match']} "
        f"tokens={row['prompt_tokens']}+{row['completion_tokens']} time={row['time']}s",
        flush=True,
    )


def run_chunk(
    *,
    adapter: LLMAdapter,
    policy_types: SortedSet[str],
    sample: list[dict[str, Any]],
    batch_size: int,
    max_n_requirements: int,
    iteration: int,
    chunk_index: int,
    timeout: float,
    max_tokens: int,
) -> dict[str, Any]:
    # EN: Run one faithful Step 1 chunk and return a writable CSV row.
    # CN: 执行一个 faithful Step 1 chunk 并返回可写入 CSV 的 row。
    expected = transform_sample_to_expected(sample)
    human_language = convert_to_human_language(sample)
    started = time.time()
    result, model_error, prompt_tokens, completion_tokens, raw_output = call_model(
        adapter=adapter,
        policy_types=policy_types,
        human_language=human_language,
        timeout=timeout,
        max_tokens=max_tokens,
    )
    row = build_empty_row(
        model_error=model_error,
        batch_size=batch_size,
        n_policy_types=len(policy_types),
        policy_types=policy_types,
        max_n_requirements=max_n_requirements,
        iteration=iteration,
        chunk_index=chunk_index,
        elapsed_seconds=time.time() - started,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        raw_output=raw_output,
    )
    if result is not None:
        score_step1_result(expected, result, row)
    return row


def run_policy_config(
    adapter: LLMAdapter,
    dataset: list[dict[str, Any]],
    policy_tuple: tuple[str, ...],
    batch_sizes: tuple[int, ...],
    n_runs: int,
    timeout: float,
    max_tokens: int,
    max_chunks_per_batch: int | None,
) -> list[dict[str, Any]]:
    # EN: Run one policy-type combination while preserving upstream chunking.
    # CN: 执行一个 policy type 组合，完全保留原脚本 chunk 机制。
    policy_types = SortedSet(policy_tuple)
    n_policy_types = len(policy_types)
    max_n_requirements = max(batch_sizes) * n_policy_types
    rows: list[dict[str, Any]] = []

    for iteration in range(n_runs):
        samples = pick_step1_sample(max_n_requirements, dataset, iteration, policy_types)
        for batch_size in batch_sizes:
            chunk_samples = list(chunk_list(samples, batch_size * n_policy_types))
            if max_chunks_per_batch is not None:
                chunk_samples = chunk_samples[:max_chunks_per_batch]

            for chunk_index, sample in enumerate(chunk_samples):
                row = run_chunk(
                    adapter=adapter,
                    policy_types=policy_types,
                    sample=sample,
                    batch_size=batch_size,
                    max_n_requirements=max_n_requirements,
                    iteration=iteration,
                    chunk_index=chunk_index,
                    timeout=timeout,
                    max_tokens=max_tokens,
                )
                rows.append(row)
                print_progress(row, n_runs, len(chunk_samples))

    return rows


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    # EN: Write CSV results.
    # CN: 写 CSV 结果。
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("No rows to write.")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_step1_translation(args: argparse.Namespace, adapter: LLMAdapter) -> Path:
    # EN: Run the full Step 1 translation reproduction and return the CSV path.
    # CN: 执行完整 Step 1 translation 复现并返回 CSV 路径。
    all_rows: list[dict[str, Any]] = []
    for policy_tuple, batch_sizes in POLICY_CONFIGS:
        all_policy_types = SortedSet(policy_tuple)
        dataset = load_step1_dataset(args.policy_file, all_policy_types)
        rows = run_policy_config(
            adapter=adapter,
            dataset=dataset,
            policy_tuple=policy_tuple,
            batch_sizes=batch_sizes,
            n_runs=args.n_runs,
            timeout=args.request_timeout,
            max_tokens=args.max_tokens,
            max_chunks_per_batch=args.max_chunks_per_batch,
        )
        all_rows.extend(rows)

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    csv_path = args.results_dir / f"result-{args.model}-step1-faithful-{timestamp}.csv"
    write_rows(csv_path, all_rows)

    avg_accuracy = sum(float(row["accuracy"]) for row in all_rows) / len(all_rows)
    exact = sum(int(row["strict_exact_match"]) for row in all_rows)
    errors = sum(1 for row in all_rows if row["model_error"] or row["format_error"])
    print("=" * 72)
    print(f"Results saved to: {csv_path}")
    print(f"Rows: {len(all_rows)}")
    print(f"Mean requirement accuracy: {avg_accuracy:.4f}")
    print(f"Strict exact match: {exact}/{len(all_rows)} = {exact / len(all_rows):.2%}")
    print(f"Errored rows: {errors}")
    print("=" * 72)
    return csv_path


def main() -> None:
    # EN: Command-line entrypoint.
    # CN: 命令行入口。
    args = parse_args()
    adapter = OpenAICompatibleAdapter.from_env(model=args.model)
    run_step1_translation(args, adapter)


if __name__ == "__main__":
    main()
