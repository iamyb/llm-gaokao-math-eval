"""
使用 pydantic-ai 从高考 PDF 图片中提取题目
用法:
    python extract_questions.py <image_dir> <output_file> [log_file]
    python extract_questions.py  # 使用默认配置
"""
import os
import sys
import json
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.messages import BinaryImage

# ==================== 从 config.py 导入配置 ====================
from config import (
    BASE_DIR, OPENAI_BASE_URL, OPENAI_API_KEY, MODEL_NAME,
    MAX_RETRIES, RETRY_DELAY, MODEL_MAX_TOKENS, PROCESS_DELAY
)

# 在导入 pydantic_ai 之前设置环境变量
os.environ["OPENAI_BASE_URL"] = OPENAI_BASE_URL
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# 默认路径（可通过命令行参数覆盖）
DEFAULT_IMAGE_DIR = os.path.join(BASE_DIR, "output_images")
DEFAULT_OUTPUT_FILE = os.path.join(BASE_DIR, "questions.jsonl")
DEFAULT_LOG_FILE = os.path.join(BASE_DIR, "extract_log.txt")

# ==============================================

log_lines = []

def log(msg):
    log_lines.append(str(msg))
    print(msg)


def sanitize_text(text: str) -> str:
    """修复模型输出里被误解析成控制字符的 LaTeX 反斜杠。"""
    return text.replace("\x08", "\\b") if text else text


# ==================== Pydantic 输出模型 ====================
class Question(BaseModel):
    """一道题目"""
    question: str = Field(description="完整题干，包含题号和选项（如有）")
    answer: str = Field(description="答案")


class QuestionsResult(BaseModel):
    """提取结果"""
    questions: list[Question] = Field(description="图片中所有题目的列表")


# ==================== Agent 定义 ====================
SYSTEM_PROMPT = """你是一个题目提取助手。请仔细分析图片，只提取其中的选择题和填空题。

要求：
1. 只提取选择题和填空题，跳过解答题、证明题等其他题型
2. 保持题目的原始格式，包括题号
3. 数学公式用 LaTeX 格式表示（行内公式用 $...$，独立公式用 $$...$$）
4. 选择题要包含所有选项
5. 如果图片中没有选择题或填空题，返回空列表"""

agent = Agent(
    model=f"openai-chat:{MODEL_NAME}",
    output_type=QuestionsResult,
    instructions=SYSTEM_PROMPT,
    model_settings={"max_tokens": MODEL_MAX_TOKENS},
)


def get_processed_images(output_file):
    """读取已处理的图片列表（断点续跑）"""
    if os.path.exists(output_file):
        processed = set()
        with open(output_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    img = data.get("_image", "")
                    if img:
                        processed.add(os.path.basename(img))
                except json.JSONDecodeError:
                    pass
        return processed
    return set()


async def process_image(image_path: str) -> list[Question]:
    """处理单张图片"""
    img_data = Path(image_path).read_bytes()
    binary_img = BinaryImage(data=img_data, media_type="image/png")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log(f"  调用模型 (尝试 {attempt}/{MAX_RETRIES})...")
            result = await agent.run(
                user_prompt=[
                    binary_img,
                    "请提取这张图片中的所有题目。",
                ],
            )
            questions = result.output.questions
            log(f"  ✓ 成功提取 {len(questions)} 道题")
            return questions
        except Exception as e:
            log(f"  ✗ 尝试 {attempt} 失败: {e}")
            if attempt < MAX_RETRIES:
                log(f"  等待 {RETRY_DELAY} 秒后重试...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                log(f"  ✗ 达到最大重试次数，跳过该图片")
                return []


async def main(image_dir=None, output_file=None, log_file=None):
    image_dir = image_dir or DEFAULT_IMAGE_DIR
    output_file = output_file or DEFAULT_OUTPUT_FILE
    log_file = log_file or DEFAULT_LOG_FILE

    log("=" * 60)
    log("题目提取脚本启动 (pydantic-ai)")
    log(f"图片目录: {image_dir}")
    log(f"输出文件: {output_file}")
    log(f"模型: {MODEL_NAME}")
    log(f"API: {os.environ['OPENAI_BASE_URL']}")
    log("=" * 60)

    if not os.path.exists(image_dir):
        log(f"✗ 图片目录不存在: {image_dir}")
        sys.exit(1)

    images = sorted([
        f for f in os.listdir(image_dir)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ])

    # 如果有合并图片，只保留合并图片，跳过所有单页
    has_merged = any(img.startswith("page_merged_") for img in images)
    if has_merged:
        merged_only = [img for img in images if img.startswith("page_merged_")]
        skipped = len(images) - len(merged_only)
        log(f"检测到合并图片，跳过 {skipped} 张单页，只处理 {len(merged_only)} 张合并图")
        images = merged_only

    if not images:
        log("✗ 未找到任何图片文件")
        sys.exit(1)

    log(f"找到 {len(images)} 张图片")

    processed = get_processed_images(output_file)
    if processed:
        log(f"检测到已处理 {len(processed)} 张图片（断点续跑）")

    append_mode = os.path.exists(output_file) and os.path.getsize(output_file) > 0
    all_questions = 0
    success_count = 0
    fail_count = 0

    with open(output_file, "a" if append_mode else "w", encoding="utf-8") as out_f:
        for img_name in images:
            img_path = os.path.join(image_dir, img_name)

            if img_name in processed:
                log(f"[跳过] {img_name} (已处理)")
                continue

            log(f"\n{'─' * 40}")
            log(f"[处理] {img_name}")

            questions = await process_image(img_path)

            if questions:
                for q in questions:
                    entry = {
                        "question": sanitize_text(q.question),
                        "answer": sanitize_text(q.answer),
                        "_image": img_name,
                    }
                    out_f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    all_questions += 1
                success_count += 1
            else:
                fail_count += 1

            await asyncio.sleep(PROCESS_DELAY)

    total_in_file = sum(1 for line in open(output_file, encoding="utf-8") if line.strip())

    log(f"\n{'=' * 60}")
    log(f"处理完成!")
    log(f"  成功: {success_count} 张图片")
    log(f"  失败: {fail_count} 张图片")
    log(f"  本次提取题目: {all_questions} 道")
    log(f"  文件总计题目: {total_in_file} 道")
    log(f"  输出文件: {output_file}")
    log(f"{'=' * 60}")

    with open(log_file, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))


if __name__ == "__main__":
    # 解析命令行参数
    image_dir = sys.argv[1] if len(sys.argv) > 1 else None
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    log_file = sys.argv[3] if len(sys.argv) > 3 else None
    asyncio.run(main(image_dir, output_file, log_file))
