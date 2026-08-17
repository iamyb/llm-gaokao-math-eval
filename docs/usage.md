简体中文 | [English](usage.en.md)

# 使用指南

## 目录结构

```
scripts/                       # 核心脚本
    config.py                  # 统一配置
    extract_questions.py       # 题目提取（PDF 图片 → JSONL）
    pdf_to_images.py           # PDF 转图片
    validate_data.py           # 数据校验管理
    add_question_type.py       # 自动标注题目类型
    view_questions.py          # 题目预览
eval/                          # 评测
    configs/                   # YAML 评测配置
    results/                   # 评测结果（自动生成）
data/
    input/2026/                # PDF 输入目录
    output/2026/               # 提取结果（待校验区，含 HTML 预览）
    final_data/2026/           # 最终数据（已校验区）
docs/images/                   # 文档用图片（试卷样例等）
build_data.py                  # 数据集构建入口
run_eval.py                    # 批量评测入口（YAML 配置驱动）
```

## 系统要求

- Python 3.10+
- 本地部署的 OpenAI 兼容 API 服务（如 llama.cpp server、vLLM、Ollama 等）

## 环境准备

```bash
pip install -r requirements.txt
cp .env.example .env   # 按需修改 EXTRACT_API_URL / EXTRACT_API_KEY / EXTRACT_MODEL
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

# 校验通过，复制到 final_data（以实际试卷名替换关键词）
python scripts/validate_data.py --approve "全国1"

# 批量复制全部
python scripts/validate_data.py --approve-all
```

### 2.5 添加题目类型（可选）

为题目自动标注类型（单选题、多选题、填空题），生成 `questions_with_type.jsonl`：

```bash
python scripts/add_question_type.py "data/output/2026/2026全国1(...)/questions.jsonl"
python scripts/add_question_type.py "data/final_data/2026/2026全国1(...)/questions.jsonl"
```

### 3. 运行评测

使用 `run_eval.py` 进行批量评测，基于 YAML 配置文件驱动，支持多模型、多次运行、自动报告生成。

```bash
# 运行评测
python run_eval.py --config eval/configs/2026_gaokao_math_ng1_qwen_vs_gemma.yaml

# 查看评测结果汇总
python run_eval.py --config eval/configs/2026_gaokao_math_ng1_qwen_vs_gemma.yaml --postprocess

# 生成 Markdown 评测报告
python run_eval.py --config eval/configs/2026_gaokao_math_ng1_qwen_vs_gemma.yaml --analyze --report
```

> 当配置中存在同一 base 模型的多个 reasoning effort 变体（如 `:low` / `:high` / 无后缀）时，`--analyze --report` 会自动生成 **Reasoning Effort 分析**（token 效率对比），详见 [Reasoning Effort 分析](reasoning_effort.md)。

### 使用 LLM 对已有结果重新评分

如果模型结果已经生成，但希望区分数学语义正确性和格式遵循率，可以使用：

```bash
python scripts/regrade_results.py --config eval/configs/2026_gaokao_math_ng1_type_online.yaml
```

该命令不会重新运行被测模型，只读取已有结果 JSON，并调用 `EVAL_GRADER_SERVER` / `EVAL_GRADER_MODEL` 指定的 LLM grader。重评分结果默认写入原输出目录名加 `-regraded`，原始 JSON 不会被覆盖；汇总报告写入 `report.regraded.md`。

每道题会记录：

- `original_correct`：原评测时的严格字符串判定；
- `semantic_correct`：LLM 判断数学答案是否正确；
- `format_correct`：LLM 判断是否遵守题目要求的答题格式；
- `grader_reason`：LLM 的简短判定理由。

报告中的数学正确率使用 `semantic_correct`，格式遵循率单独使用 `format_correct`。复杂填空答案会结合完整题目和模型原始回答判断，而不是只比较提取出的字符串。

正常运行 `scripts/llama-eval.py` 时，默认的 LLM grader 也会在每道题中保存 `semantic_correct`、`format_correct`、`normalized_answer` 和 `grader_reason`；其中 `correct` 等于 `semantic_correct`。grader 接收完整题目和模型完整回答，不接收模型返回的 `reasoning_content`。

### 3.1 YAML 配置

编辑 `eval/configs/2026_gaokao_math_ng1_qwen_vs_gemma.yaml` 配置评测参数：

```yaml
global:
  output_root: "eval/results/2026_gaokao_math_ng1_qwen_vs_gemma"
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

同一个 YAML 可以测试多个 Provider。模型级 `server` 会覆盖 `global.server`，`api_key_env` 是本机环境变量名，不是密钥本身：

```yaml
models:
  - name: "online-model-a"
    server: "https://provider-a.example.com"
    api_key_env: "PROVIDER_A_API_KEY"
    preset: "qwen"
  - name: "online-model-b"
    server: "https://provider-b.example.com"
    api_key_env: "PROVIDER_B_API_KEY"
    preset: "qwen"
  - name: "local-model"
    server: "http://localhost:8033"
    api_key_env: ""
    preset: "qwen"
```

在项目根目录 `.env` 中保存密钥：

```env
PROVIDER_A_API_KEY=your-provider-a-key
PROVIDER_B_API_KEY=your-provider-b-key
```

评测时 API Key 只从环境变量读取，并用于被测模型请求的 `Authorization: Bearer ...` 请求头；评分器仍使用原有的 `EVAL_GRADER_SERVER` 和 `EVAL_GRADER_MODEL` 配置。

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
7. **运行评测** → `python run_eval.py --config eval/configs/2026_gaokao_math_ng1_qwen_vs_gemma.yaml`
8. **查看报告** → `python run_eval.py --config eval/configs/2026_gaokao_math_ng1_qwen_vs_gemma.yaml --analyze --report`

## 配置

复制 `.env.example` 为 `.env` 并修改（或直接设置环境变量），也可以直接编辑 `scripts/config.py` 修改其余参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `EXTRACT_API_URL` | `http://localhost:8080/v1` | 题目提取 API 地址（.env 配置） |
| `EXTRACT_API_KEY` | `none` | API 密钥（.env 配置） |
| `EXTRACT_MODEL` | `your-model-name` | 题目提取模型名称（.env 配置） |
| `EVAL_SERVER` | - | 评测模型服务器地址（.env 配置） |
| `EVAL_GRADER_SERVER` | `http://localhost:10001` | 评分器服务器地址（.env 配置） |
| `EVAL_GRADER_MODEL` | - | 评分器模型名称（.env 配置） |

## 数据格式

`questions.jsonl` 每行一个 JSON 对象，包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `question` | string | 完整题干，包含题号和选项（如有） |
| `answer` | string | 标准答案 |

运行 `add_question_type.py` 后生成的 `questions_with_type.jsonl` 额外包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `question_type` | string | 题目类型：`单选题` / `多选题` / `填空题` |
