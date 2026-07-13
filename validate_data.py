"""
校验管理脚本 — 将 output/ 下校验通过的 jsonl 复制到 final_data/
用法:
    python validate_data.py --list              # 列出所有待校验文件
    python validate_data.py --status            # 查看校验状态
    python validate_data.py --approve "全国1"   # 校验通过，复制到 final_data
    python validate_data.py --approve-all       # 批量复制全部
    python validate_data.py --remove "全国1"    # 从 final_data 移除（重新校验）
"""
import os
import sys
import json
import argparse
import shutil
from config import BASE_DIR, OUTPUT_DIR, FINAL_DATA_DIR


def find_jsonl_files():
    """遍历 output/ 下所有 questions.jsonl，返回 [(year, pdf_name, output_path, final_path)]"""
    results = []
    if not os.path.exists(OUTPUT_DIR):
        return results

    for year in sorted(os.listdir(OUTPUT_DIR)):
        year_dir = os.path.join(OUTPUT_DIR, year)
        if not os.path.isdir(year_dir):
            continue
        for pdf_name in sorted(os.listdir(year_dir)):
            pdf_dir = os.path.join(year_dir, pdf_name)
            if not os.path.isdir(pdf_dir):
                continue
            output_path = os.path.join(pdf_dir, "questions.jsonl")
            if not os.path.exists(output_path):
                continue
            final_path = os.path.join(FINAL_DATA_DIR, year, pdf_name, "questions.jsonl")
            results.append((year, pdf_name, output_path, final_path))
    return results


def count_lines(filepath):
    """统计 jsonl 文件的题目数量"""
    if not os.path.exists(filepath):
        return 0
    with open(filepath, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def cmd_list():
    """列出所有待校验文件"""
    files = find_jsonl_files()
    if not files:
        print("未找到任何待校验文件")
        return

    print(f"\n{'=' * 70}")
    print(f"{'序号':<4} {'年份':<6} {'PDF 名称':<40} {'题目数':<6} {'状态'}")
    print(f"{'=' * 70}")

    for idx, (year, pdf_name, output_path, final_path) in enumerate(files, 1):
        qcount = count_lines(output_path)
        status = "✓ 已校验" if os.path.exists(final_path) else "⏳ 待校验"
        print(f"{idx:<4} {year:<6} {pdf_name:<40} {qcount:<6} {status}")

    print(f"{'=' * 70}")
    print(f"共 {len(files)} 个文件")


def cmd_status():
    """查看校验状态统计"""
    files = find_jsonl_files()
    if not files:
        print("未找到任何文件")
        return

    pending = []
    approved = []
    for year, pdf_name, output_path, final_path in files:
        if os.path.exists(final_path):
            approved.append((year, pdf_name, output_path, final_path))
        else:
            pending.append((year, pdf_name, output_path, final_path))

    print(f"\n{'=' * 50}")
    print(f"校验状态统计")
    print(f"{'=' * 50}")
    print(f"  待校验: {len(pending)} 个")
    print(f"  已校验: {len(approved)} 个")
    print(f"  总计:   {len(files)} 个")

    if pending:
        print(f"\n⏳ 待校验:")
        for year, pdf_name, _, _ in pending:
            qcount = count_lines(os.path.join(OUTPUT_DIR, year, pdf_name, "questions.jsonl"))
            print(f"  [{year}] {pdf_name} ({qcount} 题)")

    if approved:
        print(f"\n✓ 已校验:")
        for year, pdf_name, _, _ in approved:
            qcount = count_lines(os.path.join(FINAL_DATA_DIR, year, pdf_name, "questions.jsonl"))
            print(f"  [{year}] {pdf_name} ({qcount} 题)")


def _copy_without_image(src, dst):
    """复制 jsonl 文件，同时移除每条记录中的 _image 字段"""
    with open(src, "r", encoding="utf-8") as fin, \
         open(dst, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                data.pop("_image", None)
                fout.write(json.dumps(data, ensure_ascii=False) + "\n")
            except json.JSONDecodeError:
                fout.write(line + "\n")


def cmd_approve(pdf_name_filter=None, force=False):
    """将校验通过的文件复制到 final_data"""
    files = find_jsonl_files()
    if pdf_name_filter:
        files = [f for f in files if pdf_name_filter in f[1]]

    if not files:
        print(f"未找到匹配的文件 (关键词: {pdf_name_filter or '全部'})")
        return

    copied = 0
    skipped = 0
    for year, pdf_name, output_path, final_path in files:
        final_dir = os.path.dirname(final_path)
        if os.path.exists(final_path) and not force:
            print(f"  ⏭ 跳过 {pdf_name} (已存在，使用 --force 覆盖)")
            skipped += 1
            continue

        os.makedirs(final_dir, exist_ok=True)
        # 复制时移除 _image 字段
        _copy_without_image(output_path, final_path)
        qcount = count_lines(final_path)
        print(f"  ✓ {pdf_name} → final_data/{year}/{pdf_name}/ ({qcount} 题)")
        copied += 1

    print(f"\n完成: 复制 {copied} 个, 跳过 {skipped} 个")


def cmd_remove(pdf_name_filter):
    """从 final_data 移除文件（用于重新校验）"""
    files = find_jsonl_files()
    files = [f for f in files if pdf_name_filter in f[1]]

    removed = 0
    for year, pdf_name, _, final_path in files:
        if os.path.exists(final_path):
            os.remove(final_path)
            # 清理空目录
            final_dir = os.path.dirname(final_path)
            try:
                os.rmdir(final_dir)
                os.rmdir(os.path.dirname(final_dir))
            except OSError:
                pass  # 目录非空，保留
            print(f"  ✓ 已移除: {pdf_name}")
            removed += 1

    if removed == 0:
        print(f"未找到匹配的文件 (关键词: {pdf_name_filter})")
    else:
        print(f"\n共移除 {removed} 个文件")


def main():
    parser = argparse.ArgumentParser(
        description="校验管理：将 output/ 下校验通过的 jsonl 复制到 final_data/"
    )
    parser.add_argument("--list", action="store_true", help="列出所有待校验文件")
    parser.add_argument("--status", action="store_true", help="查看校验状态统计")
    parser.add_argument("--approve", type=str, nargs="?", const=True,
                        help="校验通过并复制到 final_data（不传参数则全部复制）")
    parser.add_argument("--approve-all", action="store_true", help="批量复制全部文件")
    parser.add_argument("--remove", type=str, help="从 final_data 移除（用于重新校验）")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的文件")
    args = parser.parse_args()

    if not any([args.list, args.status, args.approve, args.approve_all, args.remove]):
        parser.print_help()
        return

    if args.list:
        cmd_list()
    elif args.status:
        cmd_status()
    elif args.approve or args.approve_all:
        pdf_filter = None if (args.approve is True or args.approve_all) else args.approve
        cmd_approve(pdf_name_filter=pdf_filter, force=args.force)
    elif args.remove:
        cmd_remove(args.remove)


if __name__ == "__main__":
    main()
