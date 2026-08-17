简体中文 | [English](README.en.md)

# 高考数学试卷数据集构建与评估

从高考数学试卷（PDF）中提取客观题（选择题、填空题），构建数据集并评估本地大模型能力，包括横向不同模型之间的能力比较，以及同一模型在不同量化精度下的性能差异分析。

---

## 📊 最新评测结果

> **试卷**: 2026 全国1卷（山东、广东、湖南等 10 省） · **14 题** · 每模型 3 次运行

### 评测索引

| 日期 | 评测 |
|:----:|------|
| 2026-08-17 | [Reasoning Effort 对比（Qwen3.8 vs Qwen3.6-27b）](#reasoning-effort-对比qwen38-vs-qwen36-27b) — low / medium / high |
| 2026-08-14 | [量化对比（Qwen3.6-27b）](#量化对比qwen36-27b) — Q8 / Q6 / Q4 / Q3 / Q2 / IQ3 / IQ2 / Ternary-Bonsai-Q2 |
| 2026-08-12 | [模型对比（Muse-Glimmer-30B vs Qwen3.6-27b）](#muse-glimmer-30b-vs-qwen36-27b) |
| 2026-08-07 | [模型对比（deepseek-v4-flash vs Qwen3.6-27b）](#deepseek-v4-flash-vs-qwen36-27b) |
| 2026-07-31 | [模型对比（Qwen3.6 vs Gemma4）](#qwen36-vs-gemma4标注题目类型) |
| 2026-07-24 | [模型对比（Qwen3.6 vs Gemma4）](#qwen36-vs-gemma4标注题目类型) |
| 2026-07-24 | [量化对比（Qwen3.6-27b）](#量化对比qwen36-27b) — Q8 / Q6 / Q3 |

### 试卷样例

> 以下为 2026 全国1卷数学试卷节选

<table><tr>
<td align="center"><img src="docs/images/page_001.png" width="95%"></td>
<td align="center"><img src="docs/images/page_002.png" width="95%"></td>
</tr></table>

### 测试方法

**评测设置**：每模型对 14 题各运行 3 次，采样参数均使用各模型 HuggingFace 页面推荐的默认值。

**标注题目类型 vs 未标注**：

- **未标注**：Prompt 为 `请解答以下数学题。` + 题目原文，模型自行判断题型。
- **标注**：在 Prompt 中额外加入题型信息，变为 `请解答以下数学题（单选题）。` / `请解答以下数学题（多选题）。` / `请解答以下数学题（填空题）。`

| 模式 | Prompt 示例 |
|------|------------|
| 未标注 | `请解答以下数学题。`<br>`1. 样本数据6,8,4,5,12的中位数为（ ）`<br>`A. 5  B. 6  C. 8  D. 9` |
| 标注 | `请解答以下数学题（单选题）。`<br>`1. 样本数据6,8,4,5,12的中位数为（ ）`<br>`A. 5  B. 6  C. 8  D. 9` |

题型标注虽然只增加了几个字，但为模型提供了明确的答题格式预期（单选只需选一个字母，多选可选多个）。

> **关键发现**: 标注题目类型显著提升效果：Pass@1 从 69%~83% 提升至 95%~98%，Pass@3 从 79%~93% 提升至 100%

### 模型对比

#### Qwen3.6 vs Gemma4（标注题目类型）

<table style="border-collapse: collapse; width: 100%; text-align: center;">
<thead><tr style="border-bottom: 2px solid #ddd;">
<th width="60">排名</th><th width="310">模型</th><th width="95">Pass@1</th><th width="95">Pass@3</th><th width="110">All-Pass@3</th><th width="90">Best@3</th>
</tr></thead>
<tbody>
<tr style="border-bottom: 1px solid #eee;"><td>1</td><td style="text-align: left;">Qwen3.6-27b-UD-Q6_K_XL-MTP</td><td><b>98%</b></td><td><b>100%</b></td><td>93%</td><td><b>100%</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td>2</td><td style="text-align: left;">Qwen3.6-35b-A3B-UD-Q6_K_XL-MTP</td><td><b>98%</b></td><td><b>100%</b></td><td>93%</td><td><b>100%</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td>3</td><td style="text-align: left;">gemma-4-31B-it-UD-Q6_K_XL</td><td><b>98%</b></td><td><b>100%</b></td><td>93%</td><td><b>100%</b></td></tr>
<tr><td>4</td><td style="text-align: left;">gemma-4-26B-A4B-it-UD-Q6_K_XL</td><td><b>95%</b></td><td><b>100%</b></td><td>86%</td><td><b>100%</b></td></tr>
</tbody>
</table>

#### Qwen3.6 vs Gemma4（未标注题目类型）

<table style="border-collapse: collapse; width: 100%; text-align: center;">
<thead><tr style="border-bottom: 2px solid #ddd;">
<th width="60">排名</th><th width="310">模型</th><th width="95">Pass@1</th><th width="95">Pass@3</th><th width="110">All-Pass@3</th><th width="90">Best@3</th>
</tr></thead>
<tbody>
<tr style="border-bottom: 1px solid #eee;"><td>1</td><td style="text-align: left;">Qwen3.6-27b-UD-Q6_K_XL-MTP</td><td><b>83%</b></td><td><b>93%</b></td><td>71%</td><td><b>86%</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td>2</td><td style="text-align: left;">Qwen3.6-35b-A3B-UD-Q6_K_XL-MTP</td><td><b>81%</b></td><td><b>86%</b></td><td>71%</td><td><b>86%</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td>3</td><td style="text-align: left;">gemma-4-31B-it-UD-Q6_K_XL</td><td><b>79%</b></td><td><b>86%</b></td><td>71%</td><td><b>79%</b></td></tr>
<tr><td>4</td><td style="text-align: left;">gemma-4-26B-A4B-it-UD-Q6_K_XL</td><td><b>69%</b></td><td><b>79%</b></td><td>50%</td><td><b>79%</b></td></tr>
</tbody>
</table>

#### deepseek-v4-flash vs Qwen3.6-27b

> 未标注题目类型 · deepseek-v4-flash 为在线 API 模型（启用深度推理模式）

<table style="border-collapse: collapse; width: 100%; text-align: center;">
<thead><tr style="border-bottom: 2px solid #ddd;">
<th width="60">排名</th><th width="310">模型</th><th width="95">Pass@1</th><th width="95">Pass@3</th><th width="110">All-Pass@3</th><th width="90">Best@3</th>
</tr></thead>
<tbody>
<tr style="border-bottom: 1px solid #eee;"><td>1</td><td style="text-align: left;">deepseek-v4-flash</td><td><b>100%</b></td><td><b>100%</b></td><td><b>100%</b></td><td><b>100%</b></td></tr>
<tr><td>2</td><td style="text-align: left;">Qwen3.6-27b-UD-Q8_K_XL-MTP</td><td><b>90%</b></td><td><b>100%</b></td><td>86%</td><td><b>93%</b></td></tr>
</tbody>
</table>

#### Muse-Glimmer-30B vs Qwen3.6-27b

> 未标注题目类型 · Muse-Glimmer-30B 为本地推理模型

<table style="border-collapse: collapse; width: 100%; text-align: center;">
<thead><tr style="border-bottom: 2px solid #ddd;">
<th width="60">排名</th><th width="310">模型</th><th width="95">Pass@1</th><th width="95">Pass@3</th><th width="110">All-Pass@3</th><th width="90">Best@3</th>
</tr></thead>
<tbody>
<tr style="border-bottom: 1px solid #eee;"><td>1</td><td style="text-align: left;">Qwen3.6-27b-UD-Q8_K_XL-MTP</td><td><b>90%</b></td><td><b>100%</b></td><td><b>86%</b></td><td><b>93%</b></td></tr>
<tr><td>1</td><td style="text-align: left;">Muse-Glimmer-30B-UD-Q8_K_XL</td><td><b>90%</b></td><td><b>100%</b></td><td>79%</td><td><b>100%</b></td></tr>
</tbody>
</table>

**小结**:

- **Qwen3.6 系列综合领先**: 27b 和 35b 版本表现接近，27b 在稳定性上略占优势
- **gemma-4 系列差距缩小**: 标注类型后 Pass@3 也达到 100%，但 Pass@1 仍有差距
- **deepseek-v4-flash 全面满分**: 在线 API 模型在全部 14 题、3 次运行中达到 100% 正确率，显著领先本地模型
- **Muse-Glimmer-30B 与 Qwen3.6-27b 持平**: Pass@1 同为 90%，Best@3 甚至达到 100%，但 All-Pass@3（79%）略低于 Qwen（86%），稳定性稍弱

### 量化对比（Qwen3.6-27b）

#### 标注题目类型后

<table style="border-collapse: collapse; width: 100%; text-align: center;">
<thead><tr style="border-bottom: 2px solid #ddd;">
<th width="60">排名</th><th width="310">模型</th><th width="95">Pass@1</th><th width="95">Pass@3</th><th width="110">All-Pass@3</th><th width="90">Best@3</th>
</tr></thead>
<tbody>
<tr style="border-bottom: 1px solid #eee;"><td>1</td><td style="text-align: left;">Qwen3.6-27b-UD-Q8_K_XL-MTP</td><td><b>98%</b></td><td><b>100%</b></td><td><b>93%</b></td><td><b>100%</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td>1</td><td style="text-align: left;">Qwen3.6-27b-UD-Q6_K_XL-MTP</td><td><b>98%</b></td><td><b>100%</b></td><td><b>93%</b></td><td><b>100%</b></td></tr>
<tr><td>3</td><td style="text-align: left;">Qwen3.6-27b-UD-Q3_K_XL-MTP</td><td><b>95%</b></td><td><b>100%</b></td><td>86%</td><td><b>100%</b></td></tr>
</tbody>
</table>

#### 未标注题目类型（对比）

<table style="border-collapse: collapse; width: 100%; text-align: center;">
<thead><tr style="border-bottom: 2px solid #ddd;">
<th width="60">排名</th><th width="310">模型</th><th width="95">Pass@1</th><th width="95">Pass@3</th><th width="110">All-Pass@3</th><th width="90">Best@3</th>
</tr></thead>
<tbody>
<tr style="border-bottom: 1px solid #eee;"><td>1</td><td style="text-align: left;">Qwen3.6-27b-UD-Q8_K_XL-MTP</td><td><b>83%</b></td><td><b>100%</b></td><td><b>71%</b></td><td><b>86%</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td>1</td><td style="text-align: left;">Qwen3.6-27b-UD-Q6_K_XL-MTP</td><td><b>83%</b></td><td><b>93%</b></td><td>71%</td><td><b>86%</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td>1</td><td style="text-align: left;">Qwen3.6-27b-UD-Q4_K_XL-MTP</td><td><b>83%</b></td><td><b>93%</b></td><td>64%</td><td><b>93%</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td>4</td><td style="text-align: left;">Qwen3.6-27b-UD-IQ3_XXS-MTP</td><td><b>81%</b></td><td><b>93%</b></td><td>71%</td><td><b>86%</b></td></tr>
**小结**:

- **Q8/Q6/Q4 量化几乎无损**: 未标注时三者 Pass@1 同为 83%（Q4 与 Q8/Q6 持平），标注后 Q8 与 Q6 各项指标完全一致（Pass@1=98%, Pass@3=100%）
- **Q3 量化有明显退化**: 未标注时 Pass@1 仅 74%（比 Q8/Q6/Q4 低 9pp），标注后 Pass@1 也仅 95%（比 Q8/Q6 低 3pp）
- **低比特量化（Q2 / IQ2_XXS）退化显著**: IQ2_XXS 未标注 Pass@1 仅 67%，All-Pass@3 仅 43%；Q2 略好于 IQ2_XXS（76% vs 67%）
- **Ternary-Bonsai-27B-Q2 表现超出预期**: 作为二值化模型，Pass@1 达 81%，与 IQ3_XXS 持平，优于 Q2 和 IQ2_XXS

<tr style="border-bottom: 1px solid #eee;"><td>5</td><td style="text-align: left;">Ternary-Bonsai-27B-Q2_g64</td><td><b>81%</b></td><td><b>86%</b></td><td>71%</td><td><b>86%</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td>6</td><td style="text-align: left;">Qwen3.6-27b-UD-Q2_K_XL-MTP</td><td><b>76%</b></td><td><b>86%</b></td><td>64%</td><td><b>86%</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td>7</td><td style="text-align: left;">Qwen3.6-27b-UD-Q3_K_XL-MTP</td><td><b>74%</b></td><td><b>79%</b></td><td>64%</td><td><b>79%</b></td></tr>
<tr><td>8</td><td style="text-align: left;">Qwen3.6-27b-UD-IQ2_XXS-MTP</td><td><b>67%</b></td><td><b>86%</b></td><td>43%</td><td><b>79%</b></td></tr>
</tbody>
</table>

### Reasoning Effort 对比（Qwen3.8 vs Qwen3.6-27b）

> 均为 Q4 量化 · 每模型 low / medium / high 三档 reasoning effort · 指标说明见 [docs/reasoning_effort.md](docs/reasoning_effort.md)

#### 准确率

<table style="border-collapse: collapse; width: 100%; text-align: center;">
<thead><tr style="border-bottom: 2px solid #ddd;">
<th width="310">模型</th><th width="90">Effort</th><th width="95">Pass@1</th><th width="95">Pass@3</th><th width="110">All-Pass@3</th><th width="90">Best@3</th>
</tr></thead>
<tbody>
<tr style="border-bottom: 1px solid #eee;"><td style="text-align: left;">Qwen3.8-27b-UD-Q4_K_XL-MTP</td><td>low</td><td><b>98%</b></td><td><b>100%</b></td><td><b>93%</b></td><td><b>100%</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td style="text-align: left;">Qwen3.8-27b-UD-Q4_K_XL-MTP</td><td>medium</td><td><b>98%</b></td><td><b>100%</b></td><td><b>93%</b></td><td><b>100%</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td style="text-align: left;">Qwen3.8-27b-UD-Q4_K_XL-MTP</td><td>high</td><td><b>98%</b></td><td><b>100%</b></td><td><b>93%</b></td><td><b>100%</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td style="text-align: left;">Qwen3.6-27b-UD-Q4_K_XL-MTP</td><td>low</td><td>90%</td><td><b>100%</b></td><td>86%</td><td><b>100%</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td style="text-align: left;">Qwen3.6-27b-UD-Q4_K_XL-MTP</td><td>medium</td><td>88%</td><td>93%</td><td>79%</td><td>93%</td></tr>
<tr><td style="text-align: left;">Qwen3.6-27b-UD-Q4_K_XL-MTP</td><td>high</td><td>95%</td><td><b>100%</b></td><td>86%</td><td><b>100%</b></td></tr>
</tbody>
</table>

#### Token 效率

<table style="border-collapse: collapse; width: 100%; text-align: center;">
<thead><tr style="border-bottom: 2px solid #ddd;">
<th width="310">模型</th><th width="90">Effort</th><th width="90">Avg Tok</th><th width="90">P90 Tok</th><th width="90">~Reason%</th><th width="90">Med Tok</th>
</tr></thead>
<tbody>
<tr style="border-bottom: 1px solid #eee;"><td style="text-align: left;">Qwen3.8-27b-UD-Q4_K_XL-MTP</td><td>low</td><td><b>2729</b></td><td><b>6536</b></td><td>45%</td><td><b>1180</b></td></tr>
<tr style="border-bottom: 1px solid #eee;"><td style="text-align: left;">Qwen3.8-27b-UD-Q4_K_XL-MTP</td><td>medium</td><td>2942</td><td>6898</td><td>48%</td><td>1216</td></tr>
<tr style="border-bottom: 1px solid #eee;"><td style="text-align: left;">Qwen3.8-27b-UD-Q4_K_XL-MTP</td><td>high</td><td>7550</td><td>25378</td><td>70%</td><td>1412</td></tr>
<tr style="border-bottom: 1px solid #eee;"><td style="text-align: left;">Qwen3.6-27b-UD-Q4_K_XL-MTP</td><td>low</td><td>6060</td><td>12735</td><td>54%</td><td>3611</td></tr>
<tr style="border-bottom: 1px solid #eee;"><td style="text-align: left;">Qwen3.6-27b-UD-Q4_K_XL-MTP</td><td>medium</td><td>12987</td><td>36065</td><td>54%</td><td>5610</td></tr>
<tr><td style="text-align: left;">Qwen3.6-27b-UD-Q4_K_XL-MTP</td><td>high</td><td>7170</td><td>14383</td><td>53%</td><td>4984</td></tr>
</tbody>
</table>

> 逐题 token 对比与完整分析见 `eval/results/2026_gaokao_math_ng1_qwen38_27b_vs_qwen_36_27b/` 对应目录下的 `report.md`

**小结**:

- **Qwen3.8 全面领先且更省**: 三档 effort 的 Pass@1 均为 98%（Qwen3.6 最高仅 95%），low 的 Avg Tok 仅为 Qwen3.6 low 的 ~45%
- **Qwen3.8 的 low 在这套测评中性价比最高**: 三档准确率相同（Pass@1=98%），high 的 Avg Tok 是 low 的 ~2.8 倍（7550 vs 2729），P90 更是 ~4 倍（25378 vs 6536）；可能是题目难度饱和，low effort 已足够解出全部题目
- **Qwen3.6 的 medium 是异常点**: token 最多（12987）但 Pass@1 最低（88%），high 反而更省更准（95%）
- **两模型对 reasoning_effort 的响应不同**: Qwen3.8 的 ~Reason% 逐档上升（45%→48%→70%），response 长度基本不变（约 1.5k~2.3k token）；Qwen3.6 的 ~Reason% 几乎不变（54%→54%→53%），token 变化主要来自 response（约 2.8k→6.0k→3.4k）
- **Qwen3.8 的 high 在简单题上更省**: 对比两模型的 high 档，Qwen3.8 的 Avg Tok 略多（7550 vs 7170），但 Med Tok 少很多（1412 vs 4984），P90 Tok 多很多（25378 vs 14383）——说明 Qwen3.8 在简单题上花更少的 token，思考主要集中发力在复杂题上

> **完整报告**: 运行评测后，报告将生成在 `eval/results/<配置名>/` 目录下，包含详细的每题答题记录和评分分析

---

## 使用文档

详细的使用指南请参阅 [docs/usage.md](docs/usage.md)（英文 [docs/usage.en.md](docs/usage.en.md)），包括：

- 目录结构与系统要求
- 环境准备与快速开始
- 批量处理 PDF、数据校验、题目类型标注
- 评测配置（YAML）、运行评测与查看报告
- 环境变量配置与数据格式说明

### 快速上手

```bash
# 1. 环境准备
pip install -r requirements.txt
cp .env.example .env

# 2. 批量处理 PDF（转图片 → 提取题目 → 生成 HTML 预览）
python build_data.py --year 2026

# 3. 校验通过后复制
python scripts/validate_data.py --approve "全国1"

# 4. 运行评测
python run_eval.py --config eval/configs/2026_gaokao_math_ng1_qwen_vs_gemma.yaml
```

