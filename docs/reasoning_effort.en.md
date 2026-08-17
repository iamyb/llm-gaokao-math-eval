[简体中文](reasoning_effort.md) | English

# Reasoning Effort Analysis

`run_eval.py --analyze --report` automatically detects **different reasoning-effort variants of the same base model** in the config and generates a token-efficiency comparison (console output + a "Reasoning Effort Analysis" section in `report.md`).

## Trigger Conditions

- Effort level is identified by the **model name suffix**:
  - `:low` → `low`
  - `:high` → `high`
  - `:medium` → `medium`
  - **no suffix** → `default` (the model's default level)
- The section is generated only when the same base model (name with the suffix stripped) has **≥ 2 different levels** with existing result files; otherwise it is silently skipped and does not affect other configs.

Example config:

```yaml
models:
  - name: "Qwen3.8-27b-UD-Q4_K_XL-MTP"        # default
    preset: "qwen"
  - name: "Qwen3.8-27b-UD-Q4_K_XL-MTP:high"   # high
    preset: "qwen"
  - name: "Qwen3.8-27b-UD-Q4_K_XL-MTP:low"    # low
    preset: "qwen"
```

> Note: Windows directory names cannot contain `:`. Result directories automatically replace invalid characters with `_` (e.g. `Qwen3.8-27b-UD-Q4_K_XL-MTP_high`), and the analysis maps them back automatically.

## Metrics

Each level aggregates **all questions across all runs** of that model (e.g. 3 runs × 14 questions = 42 samples):

| Metric | Formula | Source | Meaning |
|--------|---------|--------|---------|
| **Runs** | number of result files found | directory scan | runs actually included in the stats (expected = `runs_per_model`) |
| **Avg Tok** | mean of `tokens` over all samples | `usage.completion_tokens` (exact) | average completion tokens per question (**includes reasoning**) |
| **Med Tok** | median of `tokens` | same as above | typical per-question token cost, robust to outliers |
| **P90 Tok** | 90th percentile of `tokens` | same as above | tail cost: how much the most "token-hungry" 10% of questions consume |
| **~Reason%** | estimated reasoning tokens ÷ total tokens | estimated from `reasoning_content` text length | share of output spent on reasoning; shows whether effort mainly adds thinking |
| **Avg Gen s** | mean of `t_gen_ms` ÷ 1000 | llama.cpp `timings.predicted_ms` (exact) | average generation time per question — the time cost of effort |
| **Pass@1** | correct samples ÷ total samples | `correct` field | single-run accuracy (equivalent to averaging across runs) |
| **Pass@3** | questions correct in ≥ 1 run ÷ total questions | `correct` field | "at least once correct" coverage across multiple runs |
| **Tok/Correct** | total tokens ÷ correct samples | same as above | **token cost per correct answer** — lower is cheaper |
| **Acc/1kTok** | Pass@1 ÷ (Avg Tok / 1000) | same as above | **core comparison metric**: accuracy gained per 1k tokens consumed — higher is better value |
| **Wasted Tok** | sum of `tokens` over all incorrect samples | same as above | total tokens spent without producing a correct answer |

### Per-Question Table

- One row per question, one column per effort level
- Value = **average** `tokens` for that question across runs
- `✓` = correct in at least one run, `✗` = incorrect in all runs
- Use it to find two kinds of questions:
  - **effort not worth it**: a higher level spends far more tokens without gaining correctness
  - **effort worth it**: a lower level fails but a higher level succeeds

## How ~Reason% Is Estimated

The result JSON does **not** store an exact reasoning-token count (llama.cpp's `completion_tokens` already includes reasoning tokens, but they are not stored separately), so this metric is estimated from the length of `reasoning_content`:

- CJK characters ≈ **0.65 tokens/char**
- Latin/digit words ≈ **1.3 tokens/word**

The estimate is only meant to observe the **relative change** in reasoning share (e.g. low 45% → high 70%); do not treat it as an exact value. For exact numbers, modify `scripts/llama-eval.py` to additionally record `usage.completion_tokens_details.reasoning_tokens` and re-run.

## Reading Example

```
Level     Runs   Avg Tok   Med Tok   P90 Tok  ~Reason% Avg Gen s   Pass@1   Pass@3 Tok/Correct Acc/1kTok Wasted Tok
low          3      2729      1180      6536       45%      38.4      98%     100%        2795      0.36        227
default      3      2942      1216      6898       48%      41.1      98%     100%        3014      0.33       5386
high         3      7550      1412     25378       70%     147.8      98%     100%        7735      0.13        829
```

- Accuracy is nearly identical across levels (98% / 100%), but `high`'s Avg Tok is **2.8×** that of `low`, and generation time is **3.8×**
- `high`'s P90 Tok (25378) is far above its Med Tok (1412), meaning the token spike is concentrated on a few hard questions
- `Acc/1kTok` drops from 0.36 (low) to 0.13 (high): **on this question set, `low` is the most token-efficient** — the extra thinking of `high` did not buy extra correctness

## Limitations

1. **~Reason% is an estimate** (see above); all other metrics are exact
2. Valid comparison requires the same base model, same dataset, and same seed; when comparing token efficiency across models, account for tokenizer differences
3. With few questions (e.g. 14), a single hard question's long tail output can significantly inflate the mean and P90 — read Med Tok and the per-question table together
