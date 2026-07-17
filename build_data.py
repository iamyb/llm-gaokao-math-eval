"""
数据集构建脚本 — 遍历 input/ 下所有 PDF，依次执行：转图片 → 提取题目 → 生成 HTML 预览
用法:
    python build_data.py                         # 处理所有 PDF
    python build_data.py --year 2026             # 只处理 2026 年目录
    python build_data.py --pdf 全国1              # 只处理文件名包含 "全国1" 的 PDF
    python build_data.py --skip-images           # 跳过转图片（仅提取题目）
    python build_data.py --skip-extract          # 跳过提取（仅转图片）
    python build_data.py --skip-view             # 跳过生成 HTML 预览
"""
import os
import sys
import glob
import argparse
import subprocess
from scripts.config import BASE_DIR, PDF_INPUT_DIR, OUTPUT_DIR


def find_pdfs(year=None, pdf_name=None):
    """在 input/ 目录下查找 PDF 文件，返回 (年份, 绝对路径) 列表"""
    results = []

    if year:
        search_dirs = [os.path.join(PDF_INPUT_DIR, year)]
    else:
        search_dirs = [
            os.path.join(PDF_INPUT_DIR, d)
            for d in os.listdir(PDF_INPUT_DIR)
            if os.path.isdir(os.path.join(PDF_INPUT_DIR, d))
        ]

    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            continue
        for pdf_path in sorted(glob.glob(os.path.join(search_dir, "*.pdf"))):
            if pdf_name and pdf_name not in os.path.basename(pdf_path):
                continue
            # 提取年份（相对于 input/ 的第一级目录名）
            rel = os.path.relpath(pdf_path, PDF_INPUT_DIR)
            year_name = rel.split(os.sep)[0]
            results.append((year_name, pdf_path))

    return results


def build_output_paths(year, pdf_path):
    """根据年份和PDF路径构建输出目录结构"""
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    base_output = os.path.join(OUTPUT_DIR, year, pdf_name)
    images_dir = os.path.join(base_output, "images")
    questions_file = os.path.join(base_output, "questions.jsonl")
    log_file = os.path.join(base_output, "extract_log.txt")
    return base_output, images_dir, questions_file, log_file


def run_pdf_to_images(pdf_path, images_dir, merge_pages=None):
    """调用 pdf_to_images.py 转换 PDF 为图片"""
    cmd = [sys.executable, os.path.join(BASE_DIR, "scripts", "pdf_to_images.py"), pdf_path, images_dir]
    if merge_pages:
        cmd.extend(["--merge-pages"] + [str(p) for p in merge_pages])
    print(f"  执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR)
    return result.returncode == 0


def run_extract_questions(images_dir, questions_file, log_file):
    """调用 extract_questions.py 从图片中提取题目"""
    cmd = [sys.executable, os.path.join(BASE_DIR, "scripts", "extract_questions.py"), images_dir, questions_file, log_file]
    print(f"  执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR)
    return result.returncode == 0


def run_view_questions(questions_file, output_html):
    """调用 view_questions.py 生成 HTML 预览"""
    cmd = [sys.executable, os.path.join(BASE_DIR, "scripts", "view_questions.py"), questions_file, output_html]
    print(f"  执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="批量处理高考 PDF：转图片 + 提取题目")
    parser.add_argument("--year", type=str, help="指定年份子目录（如 2026）")
    parser.add_argument("--pdf", type=str, help="指定PDF文件名（支持部分匹配）")
    parser.add_argument("--skip-images", action="store_true", help="跳过转图片步骤")
    parser.add_argument("--skip-extract", action="store_true", help="跳过提取题目步骤")
    parser.add_argument("--merge-pages", type=int, nargs="+", default=[1, 2],
                        help="合并指定的页面（1-based），默认合并第1和第2页")
    parser.add_argument("--skip-view", action="store_true", help="跳过生成 HTML 预览")
    args = parser.parse_args()

    # 检查输入目录
    if not os.path.exists(PDF_INPUT_DIR):
        print(f"✗ PDF 输入目录不存在: {PDF_INPUT_DIR}")
        print(f"   请先创建该目录并放入 PDF 文件")
        sys.exit(1)

    # 查找 PDF
    pdfs = find_pdfs(year=args.year, pdf_name=args.pdf)
    if not pdfs:
        print("✗ 未找到匹配的 PDF 文件")
        print(f"   请在 {PDF_INPUT_DIR}/<年份>/ 目录下放入 PDF")
        sys.exit(1)

    total = len(pdfs)
    print("=" * 60)
    print(f"批量处理启动")
    print(f"  找到 {total} 个 PDF 文件")
    print(f"  跳过转图片: {args.skip_images}")
    print(f"  跳过提取: {args.skip_extract}")
    print(f"  跳过预览: {args.skip_view}")
    print("=" * 60)

    success_count = 0
    fail_count = 0
    skip_count = 0

    for idx, (year, pdf_path) in enumerate(pdfs, 1):
        pdf_name = os.path.basename(pdf_path)
        base_output, images_dir, questions_file, log_file = build_output_paths(year, pdf_path)

        print(f"\n{'─' * 50}")
        print(f"[{idx}/{total}] {pdf_name}")
        print(f"  年份: {year}")
        print(f"  输出: {os.path.relpath(base_output, BASE_DIR)}")

        # 步骤 1: 转图片
        if not args.skip_images:
            print(f"  → 步骤 1: PDF 转图片 (合并页: {args.merge_pages})...")
            if not run_pdf_to_images(pdf_path, images_dir, merge_pages=args.merge_pages):
                print(f"  ✗ 转图片失败，跳过该 PDF")
                fail_count += 1
                continue

        # 步骤 2: 提取题目
        if not args.skip_extract:
            print(f"  → 步骤 2: 提取题目...")
            if not run_extract_questions(images_dir, questions_file, log_file):
                print(f"  ✗ 提取题目失败")
                fail_count += 1
                continue

        # 步骤 3: 生成 HTML 预览
        if not args.skip_view:
            output_html = os.path.join(base_output, "questions.html")
            print(f"  → 步骤 3: 生成 HTML 预览...")
            if not run_view_questions(questions_file, output_html):
                print(f"  ✗ 生成 HTML 预览失败")
                fail_count += 1
                continue

        print(f"  ✓ 完成!")
        success_count += 1

    print(f"\n{'=' * 60}")
    print(f"批量处理完成!")
    print(f"  成功: {success_count}")
    print(f"  失败: {fail_count}")
    print(f"  跳过: {skip_count}")
    print(f"  总计: {total}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
