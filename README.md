简体中文 | [English](README.en.md)

# 高考题目提取工具

从高考 PDF 试卷中自动提取选择题和填空题。

## 目录结构

```
scripts/                       # 核心脚本（config.py、提取/转图/校验/预览）
data/pdfs/2026/                 # PDF 输入目录
data/output/2026/                # 提取结果（待校验区）
data/final_data/2026/            # 最终数据（已校验区）
data/eval_results/               # 评测结果（自动生成，已加入 .gitignore）
```

## 环境准备

```bash
pip install -r requirements.txt
cp .env.example .env   # 按需修改 OPENAI_BASE_URL / OPENAI_API_KEY / MODEL_NAME
```

## 快速开始

### 1. 批量处理 PDF

```bash
# 处理所有 PDF
python batch_process.py

# 只处理 2026 年
python batch_process.py --year 2026

# 只处理特定试卷
python batch_process.py --pdf "全国1"

# 跳过转图片（仅重新提取题目）
python batch_process.py --skip-images

# 跳过提取（仅转图片）
python batch_process.py --skip-extract
```

### 2. 预览题目

```bash
# 预览所有试卷
python scripts/view_questions.py --all

# 预览指定试卷
python scripts/view_questions.py --pdf "全国1"
```

### 3. 校验管理

```bash
# 查看所有文件及状态
python scripts/validate_data.py --list

# 查看统计信息
python scripts/validate_data.py --status

# 校验通过，复制到 final_data
python scripts/validate_data.py --approve "上海"

# 批量复制全部
python scripts/validate_data.py --approve-all

# 覆盖已存在的文件
python scripts/validate_data.py --approve "上海" --force

# 从 final_data 移除（重新校验）
python scripts/validate_data.py --remove "上海"
```

### 4. 运行评测

`data/final_data/` 是已经人工校验过的数据，`llama-eval.py` 会基于它生成评测结果。结果统一保存到 `data/eval_results/` 下，并按 `年份 / 卷子 / 模型` 分层保存。

```powershell
python llama-eval.py --model Qwen3.6-35b-A3B-UD-Q6_K_XL-MTP --server http://<YOUR_SERVER_IP>:9292 --grader-type llm --grader-model qwen3.6-35b-a3b --grader-server http://localhost:10001 --dataset gaokao --dataset-path "data/final_data/2026/2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/questions.jsonl" --temperature 1.0 --top-k 20 --top-p 0.95 --min-p 0.00 --output 2026_gaokao_math_quanguo1.json --output-root data/eval_results --seed 1234 --threads 1
```

运行后会自动生成类似下面的目录：

```text
data/eval_results/
	2026/
		2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/
			Qwen3.6-35b-A3B-UD-Q6_K_XL-MTP/
				2026_gaokao_math_quanguo1.json
				2026_gaokao_math_quanguo1.json.html
```

如果同一模型多次运行，结果会写到同一个模型目录下；要避免覆盖，可以手动改 `--output` 文件名。

## 工作流程

1. **放入 PDF** → `data/pdfs/2026/` 目录
2. **批量处理** → `python batch_process.py --year 2026`
3. **人工校验** → `python scripts/view_questions.py --all` 在浏览器中检查
4. **确认通过** → `python scripts/validate_data.py --approve "关键词"`
5. **最终数据** → `data/final_data/` 目录

## 配置

复制 `.env.example` 为 `.env` 并修改（或直接设置环境变量），也可以直接编辑 `scripts/config.py` 修改其余参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_BASE_URL` | `http://localhost:8080/v1` | API 地址（.env 配置） |
| `MODEL_NAME` | `your-model-name` | 模型名称（.env 配置） |
| `MAX_RETRIES` | `3` | 最大重试次数 |
| `PROCESS_DELAY` | `1` | 图片处理间隔（秒） |

