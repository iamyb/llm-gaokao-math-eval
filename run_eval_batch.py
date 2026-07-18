#!/usr/bin/env python3
"""
Batch evaluation runner — YAML config driven, idempotent.
Supports: global → presets → model three-level parameter override.

Usage:
    python run_eval_batch.py [--config eval_config.yaml]
"""

import argparse
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


if __name__ == "__main__":
    main()
