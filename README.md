简体中文 | [English](README.en.md)

# 高考数学试卷数据集构建与评估

从数学 PDF 试卷中提取客观题（选择题、填空题），构建数据集并评估本地大模型能力。

---

## 📊 最新评测结果

> **试卷**: 2026 全国1（山东、广东、湖南等 10 省） · **14 题** · 每模型 3 次运行
>
> **注**: 本次考试在 Qwen3.6 和 Gemma4 发布之后进行，模型训练数据不包含该试卷内容。

### 标注题目类型后

| 排名 | 模型 | Pass@1 | Pass@3 | All-Pass@3 | Best@3 |
|:----:|------|:------:|:------:|:----------:|:------:|
| 1 | Qwen3.6-27b-UD-Q6_K_XL-MTP | **98%** | **100%** | 93% | **100%** |
| 2 | Qwen3.6-35b-A3B-UD-Q6_K_XL-MTP | **98%** | **100%** | 93% | **100%** |
| 3 | gemma-4-31B-it-UD-Q6_K_XL | **98%** | **100%** | 93% | **100%** |
| 4 | gemma-4-26B-A4B-it-UD-Q6_K_XL | **95%** | **100%** | 86% | **100%** |

### 未标注题目类型（对比）

| 排名 | 模型 | Pass@1 | Pass@3 | All-Pass@3 | Best@3 |
|:----:|------|:------:|:------:|:----------:|:------:|
| 1 | Qwen3.6-27b-UD-Q6_K_XL-MTP | **83%** | **93%** | 71% | **86%** |
| 2 | Qwen3.6-35b-A3B-UD-Q6_K_XL-MTP | **81%** | **86%** | 71% | **86%** |
| 3 | gemma-4-31B-it-UD-Q6_K_XL | **79%** | **86%** | 71% | **79%** |
| 4 | gemma-4-26B-A4B-it-UD-Q6_K_XL | **69%** | **79%** | 50% | **79%** |

### 关键发现

- **标注题目类型显著提升效果**: Pass@1 从 69%~83% 提升至 95%~98%，Pass@3 从 79%~93% 提升至 100%
- **Qwen3.6 系列综合领先**: 27b 和 35b 版本表现接近，27b 在稳定性上略占优势
- **gemma-4 系列差距缩小**: 标注类型后 Pass@3 也达到 100%，但 Pass@1 仍有差距
- **完整报告**: [默认配置](eval/results/eval_results/2026/2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/report.md) · [带类型标注](eval/results/eval_results_with_type/2026/2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/report.md)

---

## 目录结构

```
scripts/                       # 核心脚本（config.py、提取/转图/校验/预览等）
eval/                          # 评测配置与结果
    configs/                   # YAML 评测配置
    results/                   # 评测结果（自动生成）
data/input/2026/                # PDF 输入目录
data/output/2026/                # 提取结果（待校验区，含 HTML 预览）
data/final_data/2026/            # 最终数据（已校验区）
build_data.py                  # 数据集构建入口
run_eval.py                    # 批量评测入口（YAML 配置驱动）
```

## 环境准备

```bash
pip install -r requirements.txt
cp .env.example .env   # 按需修改 OPENAI_BASE_URL / OPENAI_API_KEY / MODEL_NAME
```

## 快速开始

### 1. 批量处理 PDF

```bash
# 处理所有 PDF（转图片 → 提取题目 → 生成 HTML 预览）
python build_data.py

# 只处理 2026 年
python build_data.py --year 2026
```

### 2. 校验管理

```bash
# 查看所有文件及状态
python scripts/validate_data.py --list

# 校验通过，复制到 final_data
python scripts/validate_data.py --approve "上海"

# 批量复制全部
python scripts/validate_data.py --approve-all
```

### 2.5 添加题目类型（可选）

为题目自动标注类型（单选题、多选题、填空题），生成 `questions_with_type.jsonl`：

```bash
python scripts/add_question_type.py "data/output/2026/2026上海/questions.jsonl"
python scripts/add_question_type.py "data/final_data/2026/2026上海/questions.jsonl"
```

### 3. 运行评测

使用 `run_eval.py` 进行批量评测，基于 YAML 配置文件驱动，支持多模型、多次运行、自动报告生成。

```bash
# 运行评测
python run_eval.py --config eval/configs/default.yaml

# 查看评测结果汇总
python run_eval.py --config eval/configs/default.yaml --postprocess

# 生成 Markdown 评测报告
python run_eval.py --config eval/configs/default.yaml --analyze --report
```

### 3.1 YAML 配置

编辑 `eval/configs/default.yaml` 配置评测参数：

```yaml
global:
  output_root: "eval/results/eval_results"
  dataset_path: "data/final_data/2026/.../questions.jsonl"
  grader_type: "llm"
  seed: 1234
  runs_per_model: 3          # 每模型运行次数
  base_output: "2026_gaokao_math_quanguo1.json"

presets:
  qwen:
    temperature: 1.0
    top_k: 20
    top_p: 0.95
    min_p: 0.0
    threads: 2
  gemma:
    temperature: 1.0
    top_k: 64
    top_p: 0.95
    min_p: 0.0
    threads: 1

models:
  - name: "Qwen3.6-35b-A3B-UD-Q6_K_XL-MTP"
    preset: "qwen"
  - name: "gemma-4-31B-it-UD-Q6_K_XL"
    preset: "gemma"
```

参数优先级：`global` → `preset` → 模型级别覆盖（server、temperature、top_k 等）。

### 3.2 评测指标

| 指标 | 含义 |
|------|------|
| **Pass@1** | 单次准确率（均值）：多次运行准确率的平均值 |
| **Pass@3** | 多次通过率：多次运行中至少有一次答对的题目占比 |
| **All-Pass@3** | 全通过率：多次运行全部答对的题目占比 |
| **Best@3** | 最佳准确率：多次运行中的最高准确率 |

## 工作流程

1. **放入 PDF** → `data/input/2026/` 目录
2. **批量处理** → `python build_data.py --year 2026`（自动转图片、提取题目、生成 HTML 预览）
3. **人工校验** → 在浏览器中打开 `data/output/2026/<试卷名>/questions.html`
4. **确认通过** → `python scripts/validate_data.py --approve "关键词"`
5. **最终数据** → `data/final_data/` 目录
6. **（可选）标注题目类型** → `python scripts/add_question_type.py`
7. **运行评测** → `python run_eval.py --config eval/configs/default.yaml`
8. **查看报告** → `python run_eval.py --config eval/configs/default.yaml --analyze --report`

## 配置

复制 `.env.example` 为 `.env` 并修改（或直接设置环境变量），也可以直接编辑 `scripts/config.py` 修改其余参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_BASE_URL` | `http://localhost:8080/v1` | 题目提取 API 地址（.env 配置） |
| `OPENAI_API_KEY` | `none` | API 密钥（.env 配置） |
| `MODEL_NAME` | `your-model-name` | 题目提取模型名称（.env 配置） |
| `EVAL_SERVER` | - | 评测模型服务器地址（.env 配置） |
| `EVAL_GRADER_SERVER` | `http://localhost:10001` | 评分器服务器地址（.env 配置） |
| `EVAL_GRADER_MODEL` | - | 评分器模型名称（.env 配置） |
| `PDF_ZOOM` | `2` | PDF 转图片缩放倍数（config.py） |
| `MAX_RETRIES` | `3` | 最大重试次数（config.py） |
| `PROCESS_DELAY` | `1` | 图片处理间隔秒数（config.py） |

