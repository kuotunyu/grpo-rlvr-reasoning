import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _notebook_code() -> str:
    notebook = json.loads(
        (ROOT / "train_grpo_colab.ipynb").read_text(encoding="utf-8")
    )
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )


def test_lora_release_uses_adapter_only_push_path():
    code = _notebook_code()

    assert "push_to_hub_merged(LORA_REPO" not in code
    assert "model.save_pretrained_merged(" in code
    assert "api.upload_folder(" not in code
    assert "api.upload_file(" not in code
    assert "ModelCard(card).push_to_hub(" not in code


def test_notebook_preflights_then_opens_reviewable_hf_prs():
    code = _notebook_code()

    assert code.index("audit_hf_file_layout(") < code.index("api.create_commit(")
    assert "create_pr=True" in code
    assert "parent_commit=" in code
    assert "PUSH_VERIFIED = verify_candidates(" in code
