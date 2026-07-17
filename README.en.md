[简体中文](README.md) | English

# Gaokao Question Extraction Toolkit

Automatically extracts multiple-choice and fill-in-the-blank questions from Chinese Gaokao (college entrance exam) PDF papers.

## Directory Structure

```
scripts/                          # Core scripts (config.py, extract/convert/validate/preview)
data/pdfs/2026/                   # PDF input directory
data/output/2026/                 # Extraction results (pending review)
data/final_data/2026/             # Final data (reviewed & approved)
data/eval_results/                # Evaluation results (auto-generated, gitignored)
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # edit OPENAI_BASE_URL / OPENAI_API_KEY / MODEL_NAME as needed
```

## Quick Start

### 1. Batch process PDFs

```bash
# Process all PDFs
python batch_process.py

# Process only the 2026 directory
python batch_process.py --year 2026

# Process only a specific paper
python batch_process.py --pdf "全国1"

# Skip image conversion (re-run extraction only)
python batch_process.py --skip-images

# Skip extraction (image conversion only)
python batch_process.py --skip-extract
```

### 2. Preview questions

```bash
# Preview all papers
python scripts/view_questions.py --all

# Preview a specific paper
python scripts/view_questions.py --pdf "全国1"
```

### 3. Validation management

```bash
# List all pending files and their status
python scripts/validate_data.py --list

# Show summary statistics
python scripts/validate_data.py --status

# Approve and copy into final_data
python scripts/validate_data.py --approve "上海"

# Batch-approve everything
python scripts/validate_data.py --approve-all

# Overwrite an existing file
python scripts/validate_data.py --approve "上海" --force

# Remove from final_data (send back for re-review)
python scripts/validate_data.py --remove "上海"
```

### 4. Run evaluation

`data/final_data/` holds the human-reviewed data; `llama-eval.py` runs evaluations against it. Results are saved under `data/eval_results/`, organized as `year / paper / model`.

```powershell
python llama-eval.py --model Qwen3.6-35b-A3B-UD-Q6_K_XL-MTP --server http://<YOUR_SERVER_IP>:9292 --grader-type llm --grader-model qwen3.6-35b-a3b --grader-server http://localhost:10001 --dataset gaokao --dataset-path "data/final_data/2026/2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/questions.jsonl" --temperature 1.0 --top-k 20 --top-p 0.95 --min-p 0.00 --output 2026_gaokao_math_quanguo1.json --output-root data/eval_results --seed 1234 --threads 1
```

This produces a directory structure like:

```text
data/eval_results/
	2026/
		2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/
			Qwen3.6-35b-A3B-UD-Q6_K_XL-MTP/
				2026_gaokao_math_quanguo1.json
				2026_gaokao_math_quanguo1.json.html
```

If you re-run the same model multiple times, results go into the same model directory; change `--output` manually to avoid overwriting previous runs.

## Workflow

1. **Drop PDFs** into `data/pdfs/2026/`
2. **Batch process** → `python batch_process.py --year 2026`
3. **Manual review** → `python scripts/view_questions.py --all`, inspect in a browser
4. **Approve** → `python scripts/validate_data.py --approve "keyword"`
5. **Final data** lands in `data/final_data/`

## Configuration

Copy `.env.example` to `.env` and edit it (or set environment variables directly). Other parameters can be edited directly in `scripts/config.py`:

| Parameter | Default | Description |
|-----------|---------|--------------|
| `OPENAI_BASE_URL` | `http://localhost:8080/v1` | API endpoint (via `.env`) |
| `MODEL_NAME` | `your-model-name` | Model name (via `.env`) |
| `MAX_RETRIES` | `3` | Max retry attempts |
| `PROCESS_DELAY` | `1` | Delay between images (seconds) |
