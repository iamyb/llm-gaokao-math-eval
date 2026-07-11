"""
统一配置文件 — 高考题目提取批量处理
"""
import os

# ==================== 路径配置 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_INPUT_DIR = os.path.join(BASE_DIR, "pdfs")       # PDF 输入根目录
OUTPUT_DIR = os.path.join(BASE_DIR, "output")         # 输出根目录

# ==================== 模型配置 ====================
OPENAI_BASE_URL = "http://192.168.0.41:9292/v1"
OPENAI_API_KEY = "none"
MODEL_NAME = "Qwen3.5-9B-UD-Q6_K_XL-MTP"

# ==================== 处理参数 ====================
PDF_ZOOM = 2                  # PDF 转图片的缩放倍数
MAX_RETRIES = 3               # 模型调用最大重试次数
RETRY_DELAY = 5               # 重试等待秒数
MODEL_MAX_TOKENS = 65536      # 模型最大输出 token 数
PROCESS_DELAY = 1             # 图片间处理间隔（秒）
