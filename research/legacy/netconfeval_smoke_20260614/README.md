# NetConfEval Early Smoke Reproduction Archive

本目录归档 2026-06-14 前一次 agent 复现尝试留下的材料。它们保留为实验历程证据，
但不再作为当前 NetConfEval 复现实验的正式入口。

## 归档内容

- `netconfeval_runner.py`
  - 早期最小 Step 1 runner。
  - 使用 OpenAI SDK 直接调用模型，绕过 LangChain。
  - 使用简化 prompt、简化样本组织和 strict exact-match 评分。

Earlier private presentation files were intentionally left out of this public
archive. The retained runner is enough to explain the early smoke-test path.

## 为什么归档

后续复现发现，早期 smoke runner 低估了模型表现，主要原因是它没有完全复用
NetConfEval 原论文的 Step 1 采样、prompt 和 `compare_result()` 逐 requirement
评分逻辑。当前正式维护的实现已经迁移到：

```text
research/netconfeval_repro/
research/netconfeval_step1_faithful.py
```

正式 Step 1 faithful reproduction 在 `n_runs=1` 下得到：

- 329 rows
- mean requirement accuracy: 99.54%
- strict exact match: 48 / 329
- errored rows: 1

因此，本目录内容应作为 early probe / legacy evidence 阅读，不应用于新的实验结论。

## 当前推荐入口

```bash
uv run --extra research netconfeval-step1 --help
```

或：

```bash
uv run --extra research python research/netconfeval_step1_faithful.py --help
```
