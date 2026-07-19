[简体中文](README.md) | English

# Gaokao Math Exam Dataset Construction and Evaluation

Extracts objective questions (multiple-choice, fill-in-the-blank) from math PDF exam papers to build datasets for evaluating local LLM capabilities.

---

## 📊 Latest Evaluation Results

> **Paper**: 2026 National 1 (Shandong, Guangdong, Hunan, etc. — 10 provinces) · **14 Questions** · 3 Runs per Model
>
> **Note**: This exam was administered after the release of Qwen3.6 and Gemma4, so the models' training data does not include this paper.

### With Question Type Labels

| Rank | Model | Pass@1 | Pass@3 | All-Pass@3 | Best@3 |
|:----:|------|:------:|:------:|:----------:|:------:|
| 1 | Qwen3.6-27b-UD-Q6_K_XL-MTP | **98%** | **100%** | 93% | **100%** |
| 2 | Qwen3.6-35b-A3B-UD-Q6_K_XL-MTP | **98%** | **100%** | 93% | **100%** |
| 3 | gemma-4-31B-it-UD-Q6_K_XL | **98%** | **100%** | 93% | **100%** |
| 4 | gemma-4-26B-A4B-it-UD-Q6_K_XL | **95%** | **100%** | 86% | **100%** |

### Without Question Type Labels (Baseline)

| Rank | Model | Pass@1 | Pass@3 | All-Pass@3 | Best@3 |
|:----:|------|:------:|:------:|:----------:|:------:|
| 1 | Qwen3.6-27b-UD-Q6_K_XL-MTP | **83%** | **93%** | 71% | **86%** |
| 2 | Qwen3.6-35b-A3B-UD-Q6_K_XL-MTP | **81%** | **86%** | 71% | **86%** |
| 3 | gemma-4-31B-it-UD-Q6_K_XL | **79%** | **86%** | 71% | **79%** |
| 4 | gemma-4-26B-A4B-it-UD-Q6_K_XL | **69%** | **79%** | 50% | **79%** |

### Key Findings

- **Question type labels significantly improve results**: Pass@1 jumps from 69%~83% to 95%~98%, Pass@3 from 79%~93% to 100%
- **Qwen3.6 series leads overall**: 27b and 35b versions are close, with 27b slightly ahead in stability
- **gemma-4 series closes the gap**: Pass@3 reaches 100% with labels, but Pass@1 still lags
- **Full reports**: [Default Config](eval/results/eval_results/2026/2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/report.md) · [With Type Labels](eval/results/eval_results_with_type/2026/2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/report.md)

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
python run_eval.py --config eval/configs/default.yaml

# Show evaluation results summary
python run_eval.py --config eval/configs/default.yaml --postprocess

# Generate Markdown evaluation report
python run_eval.py --config eval/configs/default.yaml --analyze --report
```

### 3.1 YAML Configuration

Edit `eval/configs/default.yaml` to configure evaluation parameters:

```yaml
global:
  output_root: "eval/results/eval_results"
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
7. **Run evaluation** → `python run_eval.py --config eval/configs/default.yaml`
8. **View report** → `python run_eval.py --config eval/configs/default.yaml --analyze --report`

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
