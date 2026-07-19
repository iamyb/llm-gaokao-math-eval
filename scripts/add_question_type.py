#!/usr/bin/env python3
"""
为 JSONL 数据集添加 question_type 字段。
根据题目特征自动判断：单选题、多选题、填空题。

判断逻辑：
- 有选项 A/B/C/D 且答案为单个字母 -> 单选题
- 有选项 A/B/C/D 且答案为多个字母 -> 多选题
- 无选项 -> 填空题
"""

import json
import re
import argparse
from pathlib import Path


def infer_question_type(question: str, answer: str) -> str:
    """根据题目内容和答案推断题目类型"""
    answer_stripped = answer.strip()
    
    # 检查是否有选项
    has_options = bool(re.search(r'^[A-D]\.', question, re.MULTILINE))
    
    if has_options:
        # 有选项，看答案是单个字母还是多个字母
        # 匹配纯字母答案（如 A, B, AC, ACD, BC 等）
        if re.match(r'^[A-D]+$', answer_stripped):
            if len(answer_stripped) == 1:
                return "单选题"
            else:
                return "多选题"
        return "单选题"  # 默认有选项且答案不匹配时按单选题处理
    else:
        return "填空题"


def main():
    parser = argparse.ArgumentParser(description="为 JSONL 数据集添加 question_type 字段")
    parser.add_argument("input_file", help="输入的 JSONL 文件路径")
    parser.add_argument("-o", "--output", help="输出的 JSONL 文件路径（默认在原文件旁生成 questions_with_type.jsonl）")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"文件不存在: {input_path}")
        return

    if args.output:
        output_path = Path(args.output)
    else:
        # 默认输出到同目录下的 questions_with_type.jsonl，不覆盖原文件
        output_path = input_path.parent / "questions_with_type.jsonl"

    results = []
    stats = {"单选题": 0, "多选题": 0, "填空题": 0}

    with open(input_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                print(f"第 {line_num} 行 JSON 解析失败，跳过")
                continue

            question = row.get("question", "")
            answer = row.get("answer", "")

            # 如果已有 question_type，保留不覆盖
            if "question_type" in row:
                qtype = row["question_type"]
            else:
                qtype = infer_question_type(question, answer)

            row["question_type"] = qtype
            results.append(row)
            stats[qtype] = stats.get(qtype, 0) + 1

    with open(output_path, "w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"处理完成: {len(results)} 条题目")
    print(f"  单选题: {stats.get('单选题', 0)}")
    print(f"  多选题: {stats.get('多选题', 0)}")
    print(f"  填空题: {stats.get('填空题', 0)}")
    print(f"输出到: {output_path}")


if __name__ == "__main__":
    main()
