"""
统一配置文件 — 高考题目提取批量处理
"""
import os
from dotenv import load_dotenv

# 项目根目录（本文件位于 scripts/ 下，需向上退一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 从项目根目录的 .env 文件加载环境变量（如果存在）
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ==================== 路径配置 ====================
PDF_INPUT_DIR = os.path.join(BASE_DIR, "data", "input")            # PDF 输入根目录
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output")              # 输出根目录（待校验区）
FINAL_DATA_DIR = os.path.join(BASE_DIR, "data", "final_data")      # 最终数据（已校验区）
EVAL_OUTPUT_ROOT = os.path.join(BASE_DIR, "data", "eval_results")  # 评测结果根目录

# ==================== 题目提取模型配置 ====================
# 可通过项目根目录下的 .env 文件覆盖（参考 .env.example）
EXTRACT_API_URL = os.environ.get("EXTRACT_API_URL", "http://localhost:8080/v1")
EXTRACT_API_KEY = os.environ.get("EXTRACT_API_KEY", "none")
EXTRACT_MODEL = os.environ.get("EXTRACT_MODEL", "your-model-name")

# ==================== 处理参数 ====================
PDF_ZOOM = 2                  # PDF 转图片的缩放倍数
MAX_RETRIES = 3               # 模型调用最大重试次数
RETRY_DELAY = 5               # 重试等待秒数
MODEL_MAX_TOKENS = 65536      # 模型最大输出 token 数
PROCESS_DELAY = 1             # 图片间处理间隔（秒）
