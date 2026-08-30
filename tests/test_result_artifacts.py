import json
import shutil
from pathlib import Path

from eval.verify_results import audit_repository_results


ROOT = Path(__file__).resolve().parents[1]


def test_committed_result_artifacts_match_manifest_and_metrics():
    assert audit_repository_results(ROOT) == []


def test_missing_generation_artifact_is_reported_without_a_traceback(tmp_path):
    shutil.copytree(ROOT / "results", tmp_path / "results")
    (tmp_path / "results" / "eval_generations_base.jsonl").unlink()

    errors = audit_repository_results(tmp_path)

    assert "missing artifact: results/eval_generations_base.jsonl" in errors


def test_boolean_metric_fields_require_real_json_booleans(tmp_path):
    shutil.copytree(ROOT / "results", tmp_path / "results")
    path = tmp_path / "results" / "eval_generations_base.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    row["strict_correct"] = "false"
    lines[0] = json.dumps(row, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    errors = audit_repository_results(tmp_path)

    assert "base: row 0 has invalid type for strict_correct" in errors
