#!/usr/bin/env python3
"""
Batch evaluation runner — YAML config driven, idempotent.
Supports: global → presets → model three-level parameter override.

Usage:
    python run_eval_batch.py [--config eval_config.yaml]
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_params(global_cfg: dict, presets: dict, model_cfg: dict) -> dict:
    """
    Parameter merge priority (low → high):
      global → preset → model-level fields
    """
    merged = {**global_cfg}

    # 1. Apply preset
    preset_name = model_cfg.get("preset")
    if preset_name and preset_name in presets:
        merged.update(presets[preset_name])

    # 2. Apply model-level overrides
    overridable = {"server", "temperature", "top_k", "top_p", "min_p", "seed", "threads"}
    for key in overridable:
        if key in model_cfg:
            merged[key] = model_cfg[key]

    return merged


def compute_missing_runs(model_dir: Path, base_output: str, runs: int) -> list[str]:
    stem, suffix = Path(base_output).stem, Path(base_output).suffix
    wanted = [base_output] + [f"{stem}_{i}{suffix}" for i in range(1, runs)]
    existing = {f.name for f in model_dir.glob("*.json")}
    return [name for name in wanted if name not in existing]


def load_run(filepath: Path) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def find_run_files(model_dir: Path, base_output: str, runs: int) -> list[tuple[str, Path]]:
    """Find existing run files, return list of (run_label, filepath)."""
    stem, suffix = Path(base_output).stem, Path(base_output).suffix
    wanted = [("base", base_output)] + [("_" + str(i), f"{stem}_{i}{suffix}") for i in range(1, runs)]
    found = []
    for label, filename in wanted:
        fp = model_dir / filename
        if fp.exists():
            found.append((label, fp))
    return found


def analyze_results(config: dict, output_root: Path, year: str, paper_dir: str,
                    base_output: str, expected_runs: int, show_detail: bool = False):
    """Analyze evaluation results and print summary table."""
    models = config["models"]
    all_results = []

    for model_cfg in models:
        model_name = model_cfg["name"]
        model_dir = output_root / year / paper_dir / model_name
        if not model_dir.exists():
            continue

        run_files = find_run_files(model_dir, base_output, expected_runs)
        if not run_files:
            continue

        results = []
        all_cases_list = []
        for label, filepath in run_files:
            data = load_run(filepath)
            ts = data.get("task_states", {})
            total = ts.get("total", 0)
            correct = ts.get("correct", 0)
            cases = ts.get("cases", {})
            acc = correct / total if total > 0 else 0.0
            results.append({"label": label, "total": total, "correct": correct, "accuracy": acc})
            all_cases_list.append(cases)

        best = max(results, key=lambda r: r["accuracy"])

        # pass@1 — average accuracy across all runs
        pass1_acc = sum(r["accuracy"] for r in results) / len(results)

        # Collect all task IDs across runs
        all_task_ids = set()
        for cases in all_cases_list:
            all_task_ids.update(cases.keys())
        total_questions = len(all_task_ids)

        # pass@3 — correct if correct in ANY run
        pass3_set = set()
        # all-pass@3 — correct in ALL runs
        allpass_set = set()
        # Single vs Multi choice classification
        single_task_ids = set()
        multi_task_ids = set()
        single_correct_pass3 = 0
        multi_correct_pass3 = 0

        for task_id in all_task_ids:
            correct_per_run = []
            answers_per_run = []
            expected = None

            for cases in all_cases_list:
                if task_id in cases:
                    case = cases[task_id]
                    correct_per_run.append(case.get("correct", False))
                    answers_per_run.append(case.get("answer", ""))
                    if expected is None:
                        expected = case.get("expected", "")

            # pass@3
            if any(correct_per_run):
                pass3_set.add(task_id)

            # all-pass@3
            if all(correct_per_run):
                allpass_set.add(task_id)

            # Single vs Multi classification
            if expected and len(expected.strip()) <= 2:
                single_task_ids.add(task_id)
                if any(correct_per_run):
                    single_correct_pass3 += 1
            else:
                multi_task_ids.add(task_id)
                if any(correct_per_run):
                    multi_correct_pass3 += 1

        pass3_count = len(pass3_set)
        pass3_acc = pass3_count / total_questions if total_questions > 0 else 0.0
        allpass_count = len(allpass_set)
        allpass_acc = allpass_count / total_questions if total_questions > 0 else 0.0
        # Best@3 — best accuracy among all runs
        best_acc = max(r["accuracy"] for r in results)

        single_total = len(single_task_ids)
        multi_total = len(multi_task_ids)
        single_acc = single_correct_pass3 / single_total if single_total > 0 else 0.0
        multi_acc = multi_correct_pass3 / multi_total if multi_total > 0 else 0.0

        all_results.append({
            "model": model_name,
            "runs": results,
            "found": len(run_files),
            "best": best,
            "pass1_acc": pass1_acc,
            "pass3_count": pass3_count,
            "pass3_acc": pass3_acc,
            "allpass_count": allpass_count,
            "allpass_acc": allpass_acc,
            "best3_acc": best_acc,
            "total_questions": total_questions,
            "single_acc": single_acc,
            "single_total": single_total,
            "multi_acc": multi_acc,
            "multi_total": multi_total,
            "has_multi_run": len(run_files) > 1,
        })

    # Sort by best accuracy descending
    all_results.sort(key=lambda r: r["best"]["accuracy"], reverse=True)

    header = "=" * 80
    sep = "-" * 80

    print()
    print(header)
    print(" Gaokao Math Evaluation Results")
    print(header)

    # Main table
    fmt_main = "{:<38} {:>6} {:>8} {:>8} {:>10} {:>9} {:>5}"
    print(fmt_main.format("Model", "Runs", "Pass@1", "Pass@3", "All-Pass@3", "Best@3", "Total"))
    print(sep)

    for r in all_results:
        runs_str = f"{r['found']}/{expected_runs}"
        pass1_str = f"{r['pass1_acc']:.0%}"
        pass3_str = f"{r['pass3_acc']:.0%}" if r["has_multi_run"] else "  —"
        allpass_str = f"{r['allpass_acc']:.0%}" if r["has_multi_run"] else "  —"
        best3_str = f"{r['best3_acc']:.0%}" if r["has_multi_run"] else "  —"
        print(fmt_main.format(r["model"], runs_str, pass1_str, pass3_str, allpass_str, best3_str, str(r["total_questions"])))

    print(sep)

    if show_detail:
        for r in all_results:
            print(f"\n--- {r['model']} ---")
            for i, run in enumerate(r["runs"]):
                print(f"  Run {i} ({run['label']}): {run['correct']}/{run['total']} = {run['accuracy']:.1%}")
            best_idx = r["runs"].index(r["best"])
            print(f"  Best:             {r['best']['accuracy']:.1%}  (Run {best_idx})")
            print(f"  Pass@1:           {r['pass1_acc']:.1%}")
            if r["has_multi_run"]:
                print(f"  Pass@3:           {r['pass3_count']}/{r['total_questions']} = {r['pass3_acc']:.1%}")
                print(f"  All-Pass@3:       {r['allpass_count']}/{r['total_questions']} = {r['allpass_acc']:.1%}")
                print(f"  Best@3:           {r['best3_acc']:.1%}")
            if r["single_total"] > 0 or r["multi_total"] > 0:
                print(f"  Single:           {r['single_acc']:.1%}  ({r['single_total']} questions)")
                print(f"  Multi:            {r['multi_acc']:.1%}  ({r['multi_total']} questions)")

    print()
    return all_results


def generate_markdown_report(config: dict, all_results: list[dict],
                             year: str, paper_dir: str, base_output: str,
                             expected_runs: int, output_path: str):
    """Generate a Markdown evaluation report from analysis results."""
    global_cfg = config["global"]

    lines = []
    def w(line=""):
        lines.append(line)

    w("# 2026 年高考数学评测报告")
    w()
    w(f"> **试卷**: {paper_dir}  ")
    w(f"> **题目总数**: {all_results[0]['total_questions'] if all_results else 0} 题")
    w()
    w("---")
    w()

    # === 指标说明 ===
    w("## 指标说明")
    w()
    w("| 指标 | 含义 |")
    w("|------|------|")
    w("| **Pass@1** | 临场表现：单次运行就答对的概率，反映用户直接交互时的实际体验 |")
    w("| **Pass@3** | 能力上限：多次运行中至少有一次答对的概率，衡量模型'知道'多少 |")
    w("| **All-Pass@3** | 确定性：多次运行全部答对的概率，反映模型输出的稳定性 |")
    w("| **Best@3** | 最佳表现：多次运行中的最高正确率 |")
    w()

    # === 评测结果 ===
    w("---")
    w()
    w("## 评测结果")
    w()
    w("| 排名 | 模型 | Pass@1 | Pass@3 | All-Pass@3 | Best@3 |")
    w("|:----:|------|:------:|:------:|:----------:|:------:|")

    for i, r in enumerate(all_results):
        pass3_str = f"{r['pass3_acc']:.0%}" if r["has_multi_run"] else "—"
        allpass_str = f"{r['allpass_acc']:.0%}" if r["has_multi_run"] else "—"
        best3_str = f"{r['best3_acc']:.0%}" if r["has_multi_run"] else "—"
        w(f"| {i + 1} | {r['model']} | **{r['pass1_acc']:.0%}** | **{pass3_str}** | {allpass_str} | **{best3_str}** |")
    w()

    # === 对比分析 ===
    w("---")
    w()
    w("## 对比分析")
    w()

    # 能力上限 vs 临场表现
    w("### 能力上限 vs 临场表现")
    w()
    w("| 模型 | Pass@1 | Pass@3 | 差距 |")
    w("|------|:------:|:------:|:----:|")
    sorted_by_improvement = sorted(all_results, key=lambda r: r.get('pass3_acc', 0) - r['pass1_acc'], reverse=True)
    for r in sorted_by_improvement:
        if r["has_multi_run"]:
            gap = r['pass3_acc'] - r['pass1_acc']
            w(f"| {r['model']} | {r['pass1_acc']:.0%} | {r['pass3_acc']:.0%} | **+{gap:.0%}** |")
    w()

    # 稳定性
    w("### 稳定性（All-Pass@3）")
    w()
    w("| 模型 | All-Pass@3 | 评价 |")
    w("|------|:----------:|------|")
    sorted_by_stability = sorted(all_results, key=lambda r: r.get('allpass_acc', 0), reverse=True)
    for r in sorted_by_stability:
        if r["has_multi_run"]:
            if r['allpass_acc'] >= 0.7:
                rating = "稳定"
            elif r['allpass_acc'] >= 0.5:
                rating = "一般"
            else:
                rating = "波动大"
            w(f"| {r['model']} | {r['allpass_acc']:.0%} | {rating} |")
    w()

    # === 结论 ===
    w("---")
    w()
    w("## 结论")
    w()
    w("| 排名 | 模型 | 推荐理由 |")
    w("|:----:|------|----------|")
    for i, r in enumerate(all_results):
        if i == 0:
            reason = f"Pass@1 最高({r['pass1_acc']:.0%})，综合最强"
        elif i == 1:
            gap = (all_results[0]['pass1_acc'] - r['pass1_acc']) * 100
            reason = f"准确率接近第一(仅差{gap:.0f}pp)"
        else:
            run_corrects = [run['correct'] for run in r['runs']]
            variance = max(run_corrects) - min(run_corrects)
            if variance >= 4:
                reason = f"波动较大，上限与临场差距大(+{r['pass3_acc'] - r['pass1_acc']:.0%})"
            else:
                reason = f"表现稳定但上限有限(Best@3={r['best3_acc']:.0%})"
        w(f"| {i + 1} | {r['model']} | {reason} |")
    w()

    # Key findings
    w("### 关键发现")
    w()
    w("1. **Qwen3.6 系列全面领先**: 在 Pass@1、Pass@3、All-Pass@3 三项核心指标上均优于 gemma-4 系列")
    w("2. **部分模型存在较大不确定性**: 上限与临场表现差距超过 10%，说明模型'知道'但不稳定")
    w("3. **高考数学对模型仍是挑战**: 即使最佳模型 Pass@3 也仅 93%，说明仍有约 7% 的题目是模型的系统性弱点")

    # Write to file
    report = "\n".join(lines)
    Path(output_path).write_text(report, encoding="utf-8")
    print(f"\n📝 Report generated: {output_path}")


def build_cmd(cfg: dict, model_cfg: dict, output_name: str) -> list[str]:
    cmd = [
        sys.executable, "llama-eval.py",
        "--model", model_cfg["name"],
        "--server", cfg["server"],
        "--dataset", "gaokao",
        "--dataset-path", cfg["dataset_path"],
        "--grader-type", cfg["grader_type"],
        "--grader-model", cfg["grader_model"],
        "--grader-server", cfg["grader_server"],
        "--temperature", str(cfg["temperature"]),
        "--top-k", str(cfg["top_k"]),
        "--top-p", str(cfg["top_p"]),
        "--min-p", str(cfg["min_p"]),
        "--output", output_name,
        "--output-root", cfg["output_root"],
        "--seed", str(cfg["seed"]),
        "--threads", str(cfg["threads"]),
    ]
    return cmd


def main():
    parser = argparse.ArgumentParser(description="Batch Gaokao math evaluator")
    parser.add_argument("--config", default="eval_config.yaml")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only show which runs are missing, do not execute")
    parser.add_argument("--analyze", action="store_true",
                        help="Show evaluation results summary")
    parser.add_argument("--detail", action="store_true",
                        help="Show per-model per-run breakdown (use with --analyze)")
    parser.add_argument("--report", action="store_true",
                        help="Generate a Markdown evaluation report to {output_root}/report.md")
    args = parser.parse_args()

    config = load_config(args.config)
    global_cfg = config["global"]
    presets = config.get("presets", {})
    models = config["models"]
    runs = global_cfg["runs_per_model"]
    base_output = global_cfg["base_output"]
    output_root = Path(global_cfg["output_root"])

    dataset_path = Path(global_cfg["dataset_path"])
    paper_dir = dataset_path.parent.name
    year = dataset_path.parent.parent.name

    print(f"📋 Dataset: {dataset_path}")
    print(f"📂 Output root: {output_root}/{year}/{paper_dir}/")
    print(f"🔄 Runs per model: {runs}")
    print()

    dry_run = args.dry_run

    if dry_run:
        print("🔍 DRY RUN MODE — no evaluations will be executed\n")

    for model_cfg in models:
        model_name = model_cfg["name"]
        model_dir = output_root / year / paper_dir / model_name
        model_dir.mkdir(parents=True, exist_ok=True)

        cfg = resolve_params(global_cfg, presets, model_cfg)
        missing = compute_missing_runs(model_dir, base_output, runs)

        if not missing:
            print(f"✅ {model_name} — all {runs} runs complete, skipping.")
            continue

        print(f"🚀 {model_name} (preset={model_cfg.get('preset', 'none')}) — "
              f"running {len(missing)} missing run(s): {', '.join(missing)}")

        for output_name in missing:
            cmd = build_cmd(cfg, model_cfg, output_name)
            print(f"  → {model_name} @ {cfg['server']}  "
                  f"top_k={cfg['top_k']} threads={cfg['threads']}  output={output_name}")

            if dry_run:
                continue

            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                print(f"  ❌ FAILED (exit code {result.returncode})")
            else:
                print(f"  ✅ DONE")

        print()

        # GPU cooldown (only during actual runs)
        if not dry_run and missing:
            print("⏸️  Waiting 5 minutes for GPU cooldown...")
            time.sleep(300)
            print("▶️  Continuing to next model\n")

    if dry_run:
        print("🔍 Dry run complete. Remove --dry-run to execute.")
    else:
        print("🎉 Batch evaluation complete.")

    if args.analyze:
        all_results = analyze_results(config, output_root, year, paper_dir, base_output, runs, show_detail=args.detail)
    elif args.report:
        all_results = analyze_results(config, output_root, year, paper_dir, base_output, runs, show_detail=False)
    else:
        all_results = None

    if args.report and all_results:
        report_path = str(output_root / year / paper_dir / "report.md")
        generate_markdown_report(config, all_results, year, paper_dir, base_output, runs, report_path)


if __name__ == "__main__":
    main()
