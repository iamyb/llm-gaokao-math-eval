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
        analyze_results(config, output_root, year, paper_dir, base_output, runs, show_detail=args.detail)


if __name__ == "__main__":
    main()
