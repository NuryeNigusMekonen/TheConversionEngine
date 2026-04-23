# Eval Artifacts

This directory contains the local evaluation artifacts for the Tenacious challenge:

- `score_log.json`
- `trace_log.jsonl`
- `baseline.md`
- `tau2-bench/`
- `run_tau2_retail.sh`

The official Sierra `tau2-bench` repository is checked out at `eval/tau2-bench`. The upstream project now presents itself as tau-three/tau2 version 1.0.0, but the text-mode `retail` domain is still available and is the challenge anchor.

## Run the Retail Baseline

Install `uv`, configure the provider API keys required by the model you choose, then run. The wrapper loads the project-root `.env`; if you set `OPENROUTER_MODEL=google/gemini-2.0-flash-001`, it passes `openrouter/google/gemini-2.0-flash-001` to LiteLLM automatically.

```bash
TAU2_AGENT_LLM=gpt-4.1 TAU2_USER_LLM=gpt-4.1 ./eval/run_tau2_retail.sh
```

With the project `.env` OpenRouter settings, a small smoke run is:

```bash
TAU2_NUM_TRIALS=1 TAU2_NUM_TASKS=1 ./eval/run_tau2_retail.sh --max-concurrency 1
```

For the challenge, replace both model values with the program-pinned dev-tier model. The wrapper now defaults to `--max-concurrency 1` for more stable OpenRouter runs, and it also points the evaluator helpers at the same model family unless you override `TAU2_EVAL_LLM`, `TAU2_NL_ASSERTIONS_LLM`, or `TAU2_EVAL_USER_SIMULATOR_LLM`. You can also control run size:

```bash
TAU2_NUM_TRIALS=5 TAU2_NUM_TASKS=30 ./eval/run_tau2_retail.sh
```

Results are written by tau2 into `eval/tau2-bench/data/simulations/`. The existing `score_log.json` and `trace_log.jsonl` remain labeled as local surrogate artifacts until a real tau2 run is completed with credentials.
