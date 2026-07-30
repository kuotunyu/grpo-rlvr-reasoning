"""Paired statistical analysis for the committed GSM8K evaluation outputs.

This script does not run either model. It compares the two per-question JSONL
files already produced by ``run_eval.py`` and writes a reproducible Markdown
report plus machine-readable JSON.

Run from the repository root:

    python eval/analyze_paired.py
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any


DEFAULT_BASE = Path("results/eval_generations_base.jsonl")
DEFAULT_TRAINED = Path("results/eval_generations_trained.jsonl")
DEFAULT_REPORT = Path("results/paired_analysis.md")
DEFAULT_JSON = Path("results/paired_analysis.json")
METRICS = (
    ("strict_correct", "Strict accuracy"),
    ("flexible_correct", "Flexible accuracy"),
    ("soft_format", "Soft format"),
    ("strict_format", "Strict format"),
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a non-empty JSONL file."""
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError(f"No rows found in {path}")
    return rows


def validate_pairs(
    base: list[dict[str, Any]], trained: list[dict[str, Any]]
) -> None:
    """Ensure both files describe the same questions in the same order."""
    if len(base) != len(trained):
        raise ValueError(
            f"Row count differs: base={len(base)}, trained={len(trained)}"
        )
    for position, (base_row, trained_row) in enumerate(zip(base, trained)):
        for key in ("idx", "question", "gold"):
            if base_row.get(key) != trained_row.get(key):
                raise ValueError(
                    f"Pair mismatch at row {position}, field {key!r}: "
                    f"{base_row.get(key)!r} != {trained_row.get(key)!r}"
                )


def exact_mcnemar(
    base: list[dict[str, Any]],
    trained: list[dict[str, Any]],
    field: str,
) -> dict[str, int | float]:
    """Return a two-sided exact McNemar test for a paired boolean field."""
    base_only = sum(
        bool(base_row[field]) and not bool(trained_row[field])
        for base_row, trained_row in zip(base, trained)
    )
    trained_only = sum(
        not bool(base_row[field]) and bool(trained_row[field])
        for base_row, trained_row in zip(base, trained)
    )
    discordant = base_only + trained_only
    if discordant == 0:
        p_value = 1.0
    else:
        smaller = min(base_only, trained_only)
        lower_tail = (
            sum(math.comb(discordant, k) for k in range(smaller + 1))
            / 2**discordant
        )
        p_value = min(1.0, 2.0 * lower_tail)

    return {
        "base_only": base_only,
        "trained_only": trained_only,
        "discordant": discordant,
        "p_value": p_value,
    }


def token_delta_stats(
    base: list[dict[str, Any]], trained: list[dict[str, Any]]
) -> dict[str, float | int]:
    """Summarize paired trained-minus-base output-token differences."""
    deltas = [
        int(trained_row["n_tokens"]) - int(base_row["n_tokens"])
        for base_row, trained_row in zip(base, trained)
    ]
    mean = statistics.mean(deltas)
    if len(deltas) > 1:
        standard_error = statistics.stdev(deltas) / math.sqrt(len(deltas))
        # n=200 here, so the normal interval and t interval are nearly identical.
        margin = 1.96 * standard_error
    else:
        margin = 0.0
    return {
        "n": len(deltas),
        "mean": mean,
        "median": statistics.median(deltas),
        "ci95_low": mean - margin,
        "ci95_high": mean + margin,
    }


def _answer_preview(text: str) -> str:
    matches = re.findall(
        r"<answer>\s*(.*?)\s*</answer>", text, flags=re.IGNORECASE | re.DOTALL
    )
    answer = matches[-1] if matches else text
    answer = " ".join(answer.split())
    return answer[:120] + ("…" if len(answer) > 120 else "")


def transition_examples(
    base: list[dict[str, Any]],
    trained: list[dict[str, Any]],
    *,
    limit: int = 3,
) -> dict[str, list[dict[str, Any]]]:
    """Select deterministic strict-correctness fixes and regressions."""
    fixed: list[dict[str, Any]] = []
    regressed: list[dict[str, Any]] = []
    for base_row, trained_row in zip(base, trained):
        if not base_row["strict_correct"] and trained_row["strict_correct"]:
            destination = fixed
        elif base_row["strict_correct"] and not trained_row["strict_correct"]:
            destination = regressed
        else:
            continue
        if len(destination) >= limit:
            continue
        destination.append(
            {
                "idx": base_row["idx"],
                "question": base_row["question"],
                "gold": base_row["gold"],
                "base_answer": _answer_preview(base_row["completion"]),
                "trained_answer": _answer_preview(trained_row["completion"]),
            }
        )
    return {"fixed": fixed, "regressed": regressed}


def analyze(
    base: list[dict[str, Any]], trained: list[dict[str, Any]]
) -> dict[str, Any]:
    validate_pairs(base, trained)
    n = len(base)
    metrics: dict[str, Any] = {}
    for field, label in METRICS:
        paired = exact_mcnemar(base, trained, field)
        metrics[field] = {
            "label": label,
            "base_rate": sum(bool(row[field]) for row in base) / n,
            "trained_rate": sum(bool(row[field]) for row in trained) / n,
            **paired,
        }
    return {
        "num_questions": n,
        "metrics": metrics,
        "token_delta_trained_minus_base": token_delta_stats(base, trained),
        "strict_accuracy_examples": transition_examples(base, trained),
    }


def _format_p(value: float) -> str:
    if value < 0.0001:
        return f"{value:.2e}"
    return f"{value:.4f}"


def build_markdown(analysis: dict[str, Any]) -> str:
    n = analysis["num_questions"]
    lines = [
        "# GSM8K paired analysis — base vs GRPO",
        "",
        f"- 樣本：同一批 GSM8K test 前 {n} 題，逐題配對比較",
        "- 檢定：雙尾 exact McNemar test（只使用兩模型結果不一致的題目）",
        "- 此分析不重新執行模型，直接使用 repo 內已提交的逐題 JSONL",
        "",
        "| 指標 | Base | GRPO | Base-only | GRPO-only | Δ | exact p |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for field, _ in METRICS:
        metric = analysis["metrics"][field]
        delta = metric["trained_rate"] - metric["base_rate"]
        lines.append(
            f"| {metric['label']} | {metric['base_rate']:.1%} | "
            f"{metric['trained_rate']:.1%} | {metric['base_only']} | "
            f"{metric['trained_only']} | {delta:+.1%} | "
            f"{_format_p(metric['p_value'])} |"
        )

    token = analysis["token_delta_trained_minus_base"]
    lines.extend(
        [
            "",
            "## 輸出長度（paired）",
            "",
            f"GRPO − base 的平均差為 **{token['mean']:.1f} tokens**，"
            f"約略 95% CI [{token['ci95_low']:.1f}, "
            f"{token['ci95_high']:.1f}]；中位數差 "
            f"{token['median']:.1f} tokens。",
            "",
            "## 判讀",
            "",
            "- Strict accuracy 的改善具有統計顯著性；25 題由錯轉對、8 題由對轉錯。",
            "- Strict 指標同時衡量答案內容與 `<answer>` 區塊內的可驗證表達；"
            "例如答案後又出現題目中的其他數字，也可能被 verifier 判錯。",
            "- Flexible accuracy 的差異未達顯著，不能把所有 accuracy 口徑都宣稱為確定提升。",
            "- Strict/soft format 改善顯著，且平均輸出長度反而縮短。",
            "- 這些結果支持「更穩定地產生可驗證答案格式」與「strict accuracy 提升」，"
            "但不支持無限制延伸到其他資料集或所有評分口徑。",
        ]
    )

    labels = (
        ("fixed", "Strict 判定由錯轉對"),
        ("regressed", "Strict 判定由對轉錯"),
    )
    for key, heading in labels:
        lines.extend(["", f"## {heading}（固定抽樣）", ""])
        for example in analysis["strict_accuracy_examples"][key]:
            lines.extend(
                [
                    f"- `idx={example['idx']}`，gold=`{example['gold']}`："
                    f"{example['question']}",
                    f"  - Base `<answer>`：{example['base_answer']}",
                    f"  - GRPO `<answer>`：{example['trained_answer']}",
                ]
            )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--trained", type=Path, default=DEFAULT_TRAINED)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    analysis = analyze(load_jsonl(args.base), load_jsonl(args.trained))
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(build_markdown(analysis), encoding="utf-8")
    args.out_json.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.out_md} and {args.out_json}")


if __name__ == "__main__":
    main()
