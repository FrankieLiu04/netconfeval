# AGENTS.md

## Project Shape

This repository is an independent NetConfEval paper reproduction workspace.

- Keep upstream NetConfEval code outside git at `research/netconfeval/`.
- Keep paper-compatible legacy dependencies isolated in `docker/netconfeval-paper`.
- Keep the Python runner under `research/netconfeval_repro`.
- Do not add FYP CML/MCP agent code here.
- Treat copied legacy `.env` files as untrusted input: keep only variables read
  by the reproduction scripts, document safe placeholders in `.env.example`,
  and never print real API keys or account details.
  将旧项目复制来的 `.env` 视为待清理输入：只保留复现脚本实际读取的变量，在 `.env.example` 中写安全占位值，不打印真实 API key 或账号细节。
- Keep dependency caches outside the repository in the normal user/global cache.
  Do not vendor downloaded packages into git or hide them with repo-local
  `.gitignore`; isolate paper-compatible dependencies through the Docker folder
  or lockfiles instead.
  依赖缓存放在本机用户/全局缓存中；不要把下载依赖放进仓库后用本地 `.gitignore` 隐藏，论文兼容依赖通过 Docker 目录或 lockfile 隔离。
- Runtime token settings such as `NETCONFEVAL_MAX_TOKENS` are experiment budgets,
  not provider maximum-output claims. Keep defaults conservative and raise them
  only for a named paper step or captured failure.
  `NETCONFEVAL_MAX_TOKENS` 等 token 设置是实验预算，不是 provider 最大输出声明；默认保守，只为明确论文步骤或已捕获失败上调。

## Long-Term Build Style

- Optimize for fast iteration and human readability: make the paper step
  reproducible first, and add abstraction only when two maintained runners need
  the same behavior.
  面向快速迭代和人类可读性：先让论文步骤可复现；只有两个维护中的 runner 需要同一行为时才抽象。
- Keep reproduction changes small: target one paper step, adapter behavior, or artifact format per diff, and keep most diffs under 300 changed lines unless generated outputs are involved.
  保持复现改动小而聚焦：每个 diff 默认只处理一个论文步骤、adapter 行为或产物格式，除生成输出外，尽量控制在 300 行变更以内。
- Keep functions short: target <= 40 logical lines per function; split only when the extracted helper has a clear paper/reproduction name and is reused or independently testable.
  保持函数短小：单个函数目标不超过 40 行逻辑代码；只有当 helper 有清晰论文/复现语义、可复用或可独立测试时才拆分。
- Keep scripts focused: if a script grows beyond about 300 lines, check whether it mixes model calls, parsing, scoring, and report generation.
  保持脚本聚焦：如果脚本超过约 300 行，检查它是否混合了模型调用、解析、评分和报告生成。
- Add tests only for explicit behavior: prefer 1-3 focused tests per changed parser, adapter, or artifact schema, and avoid broad regression matrices unless required to reproduce a paper table.
  只为明确行为添加测试：每个 parser、adapter 或产物 schema 变更优先写 1-3 个聚焦测试；除非复现论文表格需要，否则避免宽泛回归矩阵。
- Avoid redundant safety code: do not add fallback parsing, retry loops,
  compatibility shims, or extra regression tests unless they protect a named
  paper-compatibility boundary or an observed model/provider failure.
  避免冗余兜底代码：不要添加 fallback 解析、retry、兼容 shim 或额外回归测试，除非它们保护明确论文兼容边界或已观察模型/provider 失败。
- Keep experiment outputs separate from tests: tests should use tiny representative samples, while full reproduction outputs should live under experiment or research artifact paths.
  测试和实验输出分离：测试使用小型代表样本，完整复现输出放在 experiment 或 research 产物路径下。
- Require justification for fallback code: every retry, broad `except`, default substitution, or degraded mode must name the concrete API, data, or paper-compatibility failure it handles.
  兜底代码必须说明理由：每个 retry、宽泛 `except`、默认替换或降级模式都要写明它处理的具体 API、数据或论文兼容性失败。
- Use bilingual comments sparingly: write needed Python, shell, Docker, and env comments as adjacent `# EN:` and `# CN:` lines.
  谨慎使用中英对照注释：必要的 Python、shell、Docker 和 env 注释使用相邻的 `# EN:` 和 `# CN:` 两行。
- Do not use Python triple-quoted docstrings as comments. Module, class,
  function, runner, and test explanations must use `# EN:` / `# CN:` comments;
  preserve only true runtime strings such as prompts or upstream data samples.
  不使用 Python 三引号 docstring 作为注释；模块、类、函数、runner 和测试说明都使用
  `# EN:` / `# CN:` 注释；只保留 prompt 或上游数据样本等真实运行时字符串。
- Keep bilingual comments concise: each `# EN:` or `# CN:` line should normally
  fit within about 100 characters and explain the paper, data, or provider
  boundary rather than restating code.
  保持双语注释简洁：每行 `# EN:` 或 `# CN:` 通常不超过约 100 字符，只解释论文、数据或 provider 边界，不复述代码。
- Before coding, write down the intended behavior, touched files, expected tests, and any threshold exception. After coding, review the diff against the same four items before handoff.
  写代码前写清目标行为、涉及文件、预期测试和任何阈值例外；写完后交付前用同四项复查 diff。

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
