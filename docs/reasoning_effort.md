简体中文 | [English](reasoning_effort.en.md)

# Reasoning Effort 分析

`run_eval.py --analyze --report` 会自动检测配置中**同一 base 模型的不同 reasoning effort 变体**，并生成 token 效率对比（控制台输出 + `report.md` 中的 "Reasoning Effort 分析" 章节）。

## 触发条件

- 模型名通过**后缀**区分 effort 级别：
  - `:low` → `low`
  - `:high` → `high`
  - `:medium` → `medium`
  - **无后缀** → `default`（模型默认级别）
- 同一 base 模型（去掉后缀后的名称）下存在 **≥ 2 个不同级别**且都有结果文件时才会生成该章节；否则静默跳过，不影响其他配置。

示例配置：

```yaml
models:
  - name: "Qwen3.8-27b-UD-Q4_K_XL-MTP"        # default
    preset: "qwen"
  - name: "Qwen3.8-27b-UD-Q4_K_XL-MTP:high"   # high
    preset: "qwen"
  - name: "Qwen3.8-27b-UD-Q4_K_XL-MTP:low"    # low
    preset: "qwen"
```

> 注意：Windows 下目录名不允许包含 `:`，结果目录会自动将非法字符替换为 `_`（如 `Qwen3.8-27b-UD-Q4_K_XL-MTP_high`），分析时会自动对应回去。

## 指标说明

每个级别聚合该模型**所有 run 的所有题目**（如 3 runs × 14 题 = 42 个样本）计算：

| 指标 | 计算方式 | 数据来源 | 含义 |
|------|----------|----------|------|
| **Runs** | 找到的结果文件数 | 目录扫描 | 实际参与统计的 run 数（期望 = `runs_per_model`） |
| **Avg Tok** | 所有样本 `tokens` 的均值 | `usage.completion_tokens`（精确） | 平均每题的 completion token 数（**含 reasoning**） |
| **Med Tok** | `tokens` 的中位数 | 同上 | 典型题目的 token 消耗，不受极端值影响 |
| **P90 Tok** | `tokens` 的 90 分位数 | 同上 | 长尾开销：最"烧 token"的 10% 题目消耗多少 |
| **~Reason%** | 估算 reasoning tokens ÷ 总 tokens | `reasoning_content` 文本长度估算 | reasoning 占总输出的比例，反映 effort 是否主要加在思考上 |
| **Avg Gen s** | `t_gen_ms` 均值 ÷ 1000 | llama.cpp `timings.predicted_ms`（精确） | 平均每题生成耗时，时间维度的 effort 代价 |
| **Pass@1** | 答对样本数 ÷ 总样本数 | `correct` 字段 | 单次运行准确率（跨 run 平均的等价形式） |
| **Pass@3** | 至少一次答对的题目数 ÷ 总题数 | `correct` 字段 | 多次运行下"至少答对一次"的覆盖率 |
| **Tok/Correct** | 总 tokens ÷ 答对样本数 | 同上 | **每答对一题的 token 成本**，越低越省 |
| **Acc/1kTok** | Pass@1 ÷ (Avg Tok / 1000) | 同上 | **核心对比指标**：每消耗 1k token 换来的准确率，越高越划算 |
| **Wasted Tok** | 所有答错样本的 `tokens` 之和 | 同上 | 花掉但没换来正确性的 token 总量 |

### 逐题对比表

- 每行一道题，每列为一个 effort 级别
- 数值 = 该题在各 run 中 `tokens` 的**平均值**
- `✓` = 至少一次答对，`✗` = 全部答错
- 用途：找出两类题
  - **effort 无效**：高级别多花大量 token 但没多答对
  - **effort 有效**：低级别答错、高级别答对

## 关于 ~Reason% 的估算方法

结果 JSON 中**没有**精确的 reasoning token 数字（llama.cpp 返回的 `completion_tokens` 已包含 reasoning，但未单独拆分存储），因此该指标基于 `reasoning_content` 文本长度估算：

- 中文字符（CJK）≈ **0.65 token/字**
- 拉丁字母/数字串 ≈ **1.3 token/词**

估算值仅用于观察 reasoning 占比的**相对变化**（如 low 45% → high 70%），不要当作精确值使用。如需精确值，需要修改 `scripts/llama-eval.py` 额外记录 `usage.completion_tokens_details.reasoning_tokens` 并重跑。

## 解读示例

```
Level     Runs   Avg Tok   Med Tok   P90 Tok  ~Reason% Avg Gen s   Pass@1   Pass@3 Tok/Correct Acc/1kTok Wasted Tok
low          3      2729      1180      6536       45%      38.4      98%     100%        2795      0.36        227
default      3      2942      1216      6898       48%      41.1      98%     100%        3014      0.33       5386
high         3      7550      1412     25378       70%     147.8      98%     100%        7735      0.13        829
```

- 三个级别准确率几乎相同（98% / 100%），但 `high` 的 Avg Tok 是 `low` 的 **2.8 倍**、生成耗时 **3.8 倍**
- `high` 的 P90 Tok（25378）远高于 Med Tok（1412），说明 token 暴涨集中在少数难题上
- `Acc/1kTok` 从 low 的 0.36 降到 high 的 0.13：**这套题上 `low` 的 token 效率最高**，`high` 的额外思考没有换来额外正确率

## 局限性

1. **~Reason% 是估算值**（见上文），其余指标均为精确值
2. 对比前提是同一 base 模型、同一数据集、同一 seed，跨模型对比 token 效率时需注意 tokenizer 差异
3. 题目数较少时（如 14 题），个别难题的长尾输出会显著拉高均值和 P90，建议结合 Med Tok 和逐题表一起看
