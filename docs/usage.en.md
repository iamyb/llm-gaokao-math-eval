[简体中文](usage.md) | English

# Usage Guide

## Directory Structure

```
scripts/                          # Core scripts
    config.py                     # Shared configuration
    extract_questions.py          # Question extraction (PDF images → JSONL)
    pdf_to_images.py              # PDF to image conversion
    validate_data.py              # Data validation management
    add_question_type.py          # Auto-label question types
    view_questions.py             # Question preview
eval/                             # Evaluation
    configs/                      # YAML evaluation configs
    results/                      # Evaluation results (auto-generated)
data/
    input/2026/                   # PDF input directory
    output/2026/                  # Extraction results (pending review, with HTML preview)
    final_data/2026/              # Final data (reviewed & approved)
docs/images/                      # Documentation images (paper samples, etc.)
build_data.py                     # Dataset build entry point
run_eval.py                       # Batch evaluation entry point (YAML config driven)
```

## System Requirements

- Python 3.10+
- A locally deployed OpenAI-compatible API service (e.g., llama.cpp server, vLLM, Ollama, etc.)

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # edit EXTRACT_API_URL / EXTRACT_API_KEY / EXTRACT_MODEL as needed
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

# Approve and copy into final_data (replace keyword with actual paper name)
python scripts/validate_data.py --approve "全国1"

# Batch-approve everything
python scripts/validate_data.py --approve-all
```

### 2.5 Add question types (optional)

Automatically label question types (single-choice, multi-choice, fill-in-the-blank), generating `questions_with_type.jsonl`:

```bash
python scripts/add_question_type.py "data/output/2026/2026全国1(...)/questions.jsonl"
python scripts/add_question_type.py "data/final_data/2026/2026全国1(...)/questions.jsonl"
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
| `EXTRACT_API_URL` | `http://localhost:8080/v1` | Question extraction API endpoint (via `.env`) |
| `EXTRACT_API_KEY` | `none` | API key (via `.env`) |
| `EXTRACT_MODEL` | `your-model-name` | Question extraction model name (via `.env`) |
| `EVAL_SERVER` | - | Evaluation model server address (via `.env`) |
| `EVAL_GRADER_SERVER` | `http://localhost:10001` | Grader server address (via `.env`) |
| `EVAL_GRADER_MODEL` | - | Grader model name (via `.env`) |

## Data Format

Each line in `questions.jsonl` is a JSON object with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `question` | string | Full question text, including question number and options (if any) |
| `answer` | string | Standard answer |

Running `add_question_type.py` generates `questions_with_type.jsonl` with an additional field:

| Field | Type | Description |
|-------|------|-------------|
| `question_type` | string | Question type: `单选题` (single-choice) / `多选题` (multi-choice) / `填空题` (fill-in-the-blank) |
