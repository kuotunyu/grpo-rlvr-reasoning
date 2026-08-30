import json
import sys
from types import SimpleNamespace

from eval import run_eval


def test_default_eval_arguments_pin_dataset_and_base_model(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_eval.py"])

    args = run_eval.parse_args()

    assert args.dataset_revision == "740312add88f781978c0658806c59bc2815b9866"
    assert args.base_revision == "aa8e72537993ba99e69dfaafa59ed015b17504d1"


def test_default_trained_repo_resolves_to_frozen_weight_revision():
    assert run_eval.resolve_model_revision(
        run_eval.DEFAULT_TRAINED_MODEL, requested_revision=None
    ) == "916d51042e6e660b2b652f1442ea32f511aa4cca"
    assert run_eval.resolve_model_revision(
        "example/custom-model", requested_revision=None
    ) is None
    assert run_eval.resolve_model_revision(
        "example/custom-model", requested_revision="release-v1"
    ) == "release-v1"


def test_load_questions_forwards_the_requested_dataset_revision(monkeypatch):
    captured = {}

    class FakeDataset:
        def select(self, indices):
            captured["indices"] = list(indices)
            return [
                {"question": "q0", "answer": "#### 0"},
                {"question": "q1", "answer": "#### 1"},
            ]

    def fake_load_dataset(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeDataset()

    monkeypatch.setitem(
        sys.modules, "datasets", SimpleNamespace(load_dataset=fake_load_dataset)
    )

    questions = run_eval.load_questions(2, revision="dataset-commit")

    assert captured == {
        "args": ("openai/gsm8k", "main"),
        "kwargs": {"split": "test", "revision": "dataset-commit"},
        "indices": [0, 1],
    }
    assert questions == [("q0", "#### 0"), ("q1", "#### 1")]


def test_split_report_rejects_mismatched_dataset_revisions(tmp_path):
    base = {
        "num_questions": 200,
        "max_new_tokens": 768,
        "dataset_revision": "dataset-a",
        "decoding": "greedy",
    }
    trained = {**base, "dataset_revision": "dataset-b"}

    differences = run_eval.comparability_differences(
        base, trained, results_dir=tmp_path
    )

    assert "dataset_revision" in differences


def test_split_report_rejects_mismatched_paired_questions(tmp_path):
    settings = {
        "num_questions": 1,
        "max_new_tokens": 768,
        "dataset_revision": "dataset-a",
        "decoding": "greedy",
    }
    for tag, question in (("base", "question A"), ("trained", "question B")):
        row = {"idx": 0, "question": question, "gold": "1"}
        (tmp_path / f"eval_generations_{tag}.jsonl").write_text(
            json.dumps(row) + "\n", encoding="utf-8"
        )

    differences = run_eval.comparability_differences(
        settings, settings, results_dir=tmp_path
    )

    assert "paired_generation_records" in differences
