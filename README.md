# 高考题目提取工具

从高考 PDF 试卷中自动提取选择题和填空题。

## 目录结构

```
pdfs/2026/                    # PDF 输入目录
output/2026/                  # 提取结果（待校验区）
final_data/2026/              # 最终数据（已校验区）
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
python view_questions.py --all

# 预览指定试卷
python view_questions.py --pdf "全国1"
```

### 3. 校验管理

```bash
# 查看所有文件及状态
python validate_data.py --list

# 查看统计信息
python validate_data.py --status

# 校验通过，复制到 final_data
python validate_data.py --approve "上海"

# 批量复制全部
python validate_data.py --approve-all

# 覆盖已存在的文件
python validate_data.py --approve "上海" --force

# 从 final_data 移除（重新校验）
python validate_data.py --remove "上海"
```

## 工作流程

1. **放入 PDF** → `pdfs/2026/` 目录
2. **批量处理** → `python batch_process.py --year 2026`
3. **人工校验** → `python view_questions.py --all` 在浏览器中检查
4. **确认通过** → `python validate_data.py --approve "关键词"`
5. **最终数据** → `final_data/` 目录

## 配置

编辑 `config.py` 修改模型参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_BASE_URL` | `http://192.168.0.41:9292/v1` | API 地址 |
| `MODEL_NAME` | `Qwen3.5-9B-UD-Q6_K_XL-MTP` | 模型名称 |
| `MAX_RETRIES` | `3` | 最大重试次数 |
| `PROCESS_DELAY` | `1` | 图片处理间隔（秒） |
