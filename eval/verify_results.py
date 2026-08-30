"""Offline integrity and consistency checks for committed evaluation evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "idx",
    "question",
    "gold",
    "completion",
    "n_tokens",
    "strict_correct",
    "flexible_correct",
    "soft_format",
    "strict_format",
}
BOOLEAN_METRICS = (
    ("strict_correct", "strict_accuracy"),
    ("flexible_correct", "flexible_accuracy"),
    ("soft_format", "soft_format_rate"),
    ("strict_format", "strict_format_rate"),
)
FIELD_TYPES = {
    "idx": int,
    "question": str,
    "gold": (int, float),
    "completion": str,
    "n_tokens": int,
    "strict_correct": bool,
    "flexible_correct": bool,
    "soft_format": bool,
    "strict_format": bool,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _audit_generation_file(
    *, tag: str, rows: list[dict[str, Any]], metrics: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if not rows:
        return [f"{tag}: generation file is empty"]
    expected_indices = list(range(len(rows)))
    actual_indices = [row.get("idx") for row in rows]
    if actual_indices != expected_indices:
        errors.append(f"{tag}: idx must be contiguous from 0")
    schema_valid = True
    for position, row in enumerate(rows):
        if set(row) != REQUIRED_FIELDS:
            errors.append(f"{tag}: row {position} has an unexpected schema")
            schema_valid = False
            break
        for field, expected_type in FIELD_TYPES.items():
            value = row[field]
            type_valid = isinstance(value, expected_type)
            if field in {"idx", "gold", "n_tokens"} and isinstance(value, bool):
                type_valid = False
            if not type_valid:
                errors.append(f"{tag}: row {position} has invalid type for {field}")
                schema_valid = False
                break
        if not schema_valid:
            break
    if metrics.get("num_questions") != len(rows):
        errors.append(f"{tag}: metrics num_questions does not match JSONL rows")
    if not schema_valid:
        return errors
    for row_key, metric_key in BOOLEAN_METRICS:
        observed = sum(bool(row[row_key]) for row in rows) / len(rows)
        if not math.isclose(observed, float(metrics.get(metric_key, math.nan))):
            errors.append(f"{tag}: {metric_key} does not match JSONL")
    mean_tokens = sum(int(row["n_tokens"]) for row in rows) / len(rows)
    if not math.isclose(mean_tokens, float(metrics.get("mean_output_tokens", math.nan))):
        errors.append(f"{tag}: mean_output_tokens does not match JSONL")
    return errors


def audit_repository_results(root: Path) -> list[str]:
    """Verify hashes, schemas, pairing, and aggregate metrics without a GPU."""
    results = root / "results"
    manifest_path = results / "artifact_manifest.json"
    if not manifest_path.exists():
        return ["missing results/artifact_manifest.json"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    for artifact in manifest.get("artifacts", []):
        path = root / artifact["path"]
        if not path.is_file():
            errors.append(f"missing artifact: {artifact['path']}")
            continue
        if path.stat().st_size != artifact["bytes"]:
            errors.append(f"size mismatch: {artifact['path']}")
        if _sha256(path) != artifact["sha256"]:
            errors.append(f"sha256 mismatch: {artifact['path']}")

    loaded: dict[str, list[dict[str, Any]]] = {}
    for tag in ("base", "trained"):
        generations_path = results / f"eval_generations_{tag}.jsonl"
        metrics_path = results / f"eval_metrics_{tag}.json"
        if not generations_path.is_file() or not metrics_path.is_file():
            continue
        rows = _load_jsonl(generations_path)
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        loaded[tag] = rows
        errors.extend(_audit_generation_file(tag=tag, rows=rows, metrics=metrics))

    if set(loaded) != {"base", "trained"}:
        return errors
    if len(loaded["base"]) != len(loaded["trained"]):
        errors.append("paired JSONL row counts differ")
    else:
        for position, (base, trained) in enumerate(
            zip(loaded["base"], loaded["trained"])
        ):
            if any(base[key] != trained[key] for key in ("idx", "question", "gold")):
                errors.append(f"paired identity mismatch at row {position}")
                break
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    errors = audit_repository_results(args.root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("Result artifacts match the manifest and aggregate metrics.")


if __name__ == "__main__":
    main()
