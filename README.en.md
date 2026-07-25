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
<td align="center"><img src="docs/images/page_001.png" width="95%"></td>
<td align="center"><img src="docs/images/page_002.png" width="95%"></td>
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
- **Full reports**: After running evaluation, reports are generated under `eval/results/<config-name>/` with detailed per-question records and scoring analysis

---

## Usage Documentation

For detailed usage instructions, see [docs/usage.en.md](docs/usage.en.md) (中文 [docs/usage.md](docs/usage.md)), including:

- Directory structure & system requirements
- Setup & quick start
- Batch PDF processing, data validation, question type labeling
- Evaluation configuration (YAML), running evaluations & viewing reports
- Environment variables & data format

### Quick Start

```bash
# 1. Setup
pip install -r requirements.txt
cp .env.example .env

# 2. Batch process PDFs (convert to images → extract questions → generate HTML preview)
python build_data.py --year 2026

# 3. Approve & copy after review
python scripts/validate_data.py --approve "全国1"

# 4. Run evaluation
python run_eval.py --config eval/configs/2026_gaokao_math_ng1_qwen_vs_gemma.yaml
```
