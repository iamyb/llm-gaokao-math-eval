[简体中文](README.md) | English

# Gaokao Math Exam Dataset Construction and Evaluation

Extracts objective questions (multiple-choice, fill-in-the-blank) from Gaokao (China's national college entrance examination) math PDF exam papers to build datasets for evaluating local LLM capabilities, including cross-model capability comparisons and performance analysis of the same model across different quantization levels.

---

## 📊 Latest Evaluation Results

> **Paper**: 2026 National 1 (Shandong, Guangdong, Hunan, etc. — 10 provinces) · **14 Questions** · 3 Runs per Model
>
> **Note**: This exam was administered after the release of Qwen3.6 and Gemma4, so the models' training data does not include this paper.

### Paper Sample

> Excerpt from the 2026 National 1 Math Exam Paper

<table><tr>
<td align="center"><img src="data/output/2026/2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/images/page_001.png" width="95%"></td>
<td align="center"><img src="data/output/2026/2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/images/page_002.png" width="95%"></td>
</tr></table>

### Methodology

**Evaluation Setup**: Each model runs 3 times on 14 questions, with sampling parameters using the default values recommended on each model's HuggingFace page.

**With vs Without Question Type Labels**:

- **Without labels**: Prompt is `请解答以下数学题。` + question text, the model infers the question type on its own.
- **With labels**: The question type is added to the prompt, becoming `请解答以下数学题（单选题）。` / `请解答以下数学题（多选题）。` / `请解答以下数学题（填空题）。`

| Mode | Prompt Example |
|------|---------------|
| Without labels | `请解答以下数学题。`<br>`1. 样本数据6,8,4,5,12的中位数为（ ）`<br>`A. 5  B. 6  C. 8  D. 9` |
| With labels | `请解答以下数学题（单选题）。`<br>`1. 样本数据6,8,4,5,12的中位数为（ ）`<br>`A. 5  B. 6  C. 8  D. 9` |

Adding the question type label costs only a few extra characters in the prompt, but gives the model a clear expectation of the answer format (single letter for single-choice, multiple letters for multi-choice).

### Model Comparison (Qwen vs Gemma)

#### With Question Type Labels

| Rank | Model | Pass@1 | Pass@3 | All-Pass@3 | Best@3 |
|:----:|------|:------:|:------:|:----------:|:------:|
| 1 | Qwen3.6-27b-UD-Q6_K_XL-MTP | **98%** | **100%** | 93% | **100%** |
| 2 | Qwen3.6-35b-A3B-UD-Q6_K_XL-MTP | **98%** | **100%** | 93% | **100%** |
| 3 | gemma-4-31B-it-UD-Q6_K_XL | **98%** | **100%** | 93% | **100%** |
| 4 | gemma-4-26B-A4B-it-UD-Q6_K_XL | **95%** | **100%** | 86% | **100%** |

#### Without Question Type Labels (Baseline)

| Rank | Model | Pass@1 | Pass@3 | All-Pass@3 | Best@3 |
|:----:|------|:------:|:------:|:----------:|:------:|
| 1 | Qwen3.6-27b-UD-Q6_K_XL-MTP | **83%** | **93%** | 71% | **86%** |
| 2 | Qwen3.6-35b-A3B-UD-Q6_K_XL-MTP | **81%** | **86%** | 71% | **86%** |
| 3 | gemma-4-31B-it-UD-Q6_K_XL | **79%** | **86%** | 71% | **79%** |
| 4 | gemma-4-26B-A4B-it-UD-Q6_K_XL | **69%** | **79%** | 50% | **79%** |

### Quantization Comparison (Qwen3.6-27b)

#### With Question Type Labels

| Rank | Model | Pass@1 | Pass@3 | All-Pass@3 | Best@3 |
|:----:|------|:------:|:------:|:----------:|:------:|
| 1 | Qwen3.6-27b-UD-Q6_K_XL-MTP | **98%** | **100%** | **93%** | **100%** |
| 1 | Qwen3.6-27b-UD-Q8_K_XL-MTP | **98%** | **100%** | **93%** | **100%** |
| 3 | Qwen3.6-27b-UD-Q3_K_XL-MTP | **95%** | **100%** | 86% | **100%** |

#### Without Question Type Labels (Baseline)

| Rank | Model | Pass@1 | Pass@3 | All-Pass@3 | Best@3 |
|:----:|------|:------:|:------:|:----------:|:------:|
| 1 | Qwen3.6-27b-UD-Q8_K_XL-MTP | **83%** | **100%** | **71%** | **86%** |
| 2 | Qwen3.6-27b-UD-Q6_K_XL-MTP | **83%** | **93%** | 71% | **86%** |
| 3 | Qwen3.6-27b-UD-Q3_K_XL-MTP | **74%** | **79%** | 64% | **79%** |

### Key Findings

- **Question type labels significantly improve results**: Pass@1 jumps from 69%~83% to 95%~98%, Pass@3 from 79%~93% to 100%
- **Qwen3.6 series leads overall**: 27b and 35b versions are close, with 27b slightly ahead in stability
- **gemma-4 series closes the gap**: Pass@3 reaches 100% with labels, but Pass@1 still lags
- **Q8/Q6 quantization is nearly lossless**: With type labels, Q8 and Q6 are identical across all metrics (Pass@1=98%, Pass@3=100%), making Q6 the best value choice with smaller model size
- **Q3 quantization shows noticeable degradation**: Without labels, Pass@1 drops to 74% (9pp behind Q6/Q8); with labels, Pass@1 is 95% (3pp behind), and All-Pass@3 is the lowest
- **Full reports**: [Model Comparison](eval/results/2026_gaokao_math_ng1_qwen_vs_gemma/2026/2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/report.md) · [Model Comparison (With Types)](eval/results/2026_gaokao_math_ng1_type_qwen_vs_gemma/2026/2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/report.md) · [Quantization Comparison](eval/results/2026_gaokao_math_ng1_qwen_36_27b_quant/2026/2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/report.md) · [Quantization Comparison (With Types)](eval/results/2026_gaokao_math_ng1_type_qwen_36_27b_quant/2026/2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/report.md)

---

## Directory Structure

```
scripts/                          # Core scripts (config.py, extract/convert/validate/preview, etc.)
eval/                             # Evaluation configuration and results
    configs/                      # YAML evaluation configs
    results/                      # Evaluation results (auto-generated)
data/input/2026/                  # PDF input directory
data/output/2026/                 # Extraction results (pending review, with HTML preview)
data/final_data/2026/             # Final data (reviewed & approved)
build_data.py                     # Dataset build entry point
run_eval.py                       # Batch evaluation entry point (YAML config driven)
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # edit OPENAI_BASE_URL / OPENAI_API_KEY / MODEL_NAME as needed
```

## Quick Start

### 1. Batch process PDFs

```bash
# Process all PDFs (convert to images → extract questions → generate HTML preview)
python build_data.py

# Process only the 2026 directory
python build_data.py --year 2026
```

### 2. Validation management

```bash
# List all pending files and their status
python scripts/validate_data.py --list

# Approve and copy into final_data
python scripts/validate_data.py --approve "上海"

# Batch-approve everything
python scripts/validate_data.py --approve-all
```

### 2.5 Add question types (optional)

Automatically label question types (single-choice, multi-choice, fill-in-the-blank), generating `questions_with_type.jsonl`:

```bash
python scripts/add_question_type.py "data/output/2026/2026上海/questions.jsonl"
python scripts/add_question_type.py "data/final_data/2026/2026上海/questions.jsonl"
```

### 3. Run evaluation

Use `run_eval.py` for batch evaluation, driven by YAML configuration files, supporting multiple models, multiple runs, and automatic report generation.

```bash
# Run evaluation
python run_eval.py --config eval/configs/2026_gaokao_math_ng1_qwen_vs_gemma.yaml

# Show evaluation results summary
python run_eval.py --config eval/configs/2026_gaokao_math_ng1_qwen_vs_gemma.yaml --postprocess

# Generate Markdown evaluation report
python run_eval.py --config eval/configs/2026_gaokao_math_ng1_qwen_vs_gemma.yaml --analyze --report
```

### 3.1 YAML Configuration

Edit `eval/configs/2026_gaokao_math_ng1_qwen_vs_gemma.yaml` to configure evaluation parameters:

```yaml
global:
  output_root: "eval/results/2026_gaokao_math_ng1_qwen_vs_gemma"
  dataset_path: "data/final_data/2026/.../questions.jsonl"
  grader_type: "llm"
  seed: 1234
  runs_per_model: 3          # number of runs per model
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

Parameter priority: `global` → `preset` → model-level overrides (server, temperature, top_k, etc.).

### 3.2 Evaluation Metrics

| Metric | Description |
|--------|-------------|
| **Pass@1** | Mean single-run accuracy: average accuracy across all runs |
| **Pass@3** | Multi-run pass rate: fraction of questions answered correctly in at least one run |
| **All-Pass@3** | All-run pass rate: fraction of questions answered correctly in all runs |
| **Best@3** | Best accuracy: highest accuracy among all runs |

## Workflow

1. **Drop PDFs** into `data/input/2026/`
2. **Batch process** → `python build_data.py --year 2026` (convert images, extract questions, generate HTML preview)
3. **Manual review** → open `data/output/2026/<paper>/questions.html` in a browser
4. **Approve** → `python scripts/validate_data.py --approve "keyword"`
5. **Final data** → lands in `data/final_data/`
6. **(Optional) Label question types** → `python scripts/add_question_type.py`
7. **Run evaluation** → `python run_eval.py --config eval/configs/2026_gaokao_math_ng1_qwen_vs_gemma.yaml`
8. **View report** → `python run_eval.py --config eval/configs/2026_gaokao_math_ng1_qwen_vs_gemma.yaml --analyze --report`

## Configuration

Copy `.env.example` to `.env` and edit it (or set environment variables directly). Other parameters can be edited in `scripts/config.py`:

| Parameter | Default | Description |
|-----------|---------|--------------|
| `OPENAI_BASE_URL` | `http://localhost:8080/v1` | Question extraction API endpoint (via `.env`) |
| `OPENAI_API_KEY` | `none` | API key (via `.env`) |
| `MODEL_NAME` | `your-model-name` | Question extraction model name (via `.env`) |
| `EVAL_SERVER` | - | Evaluation model server address (via `.env`) |
| `EVAL_GRADER_SERVER` | `http://localhost:10001` | Grader server address (via `.env`) |
| `EVAL_GRADER_MODEL` | - | Grader model name (via `.env`) |
| `PDF_ZOOM` | `2` | PDF-to-image zoom factor (config.py) |
| `MAX_RETRIES` | `3` | Max retry attempts (config.py) |
| `PROCESS_DELAY` | `1` | Delay between images in seconds (config.py) |
