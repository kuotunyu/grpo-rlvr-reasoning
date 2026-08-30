import hashlib
from pathlib import Path

from hf_release import (
    audit_hf_file_layout,
    model_card_header,
    model_card_legal_section,
)


ROOT = Path(__file__).resolve().parents[1]
QWEN_LICENSE_SHA256 = "ef52482bb785733093dc9a2e8edd8e764c77d12d8e9d8f10a80c9b547d32d0f9"


def test_model_card_header_uses_qwen_research_license_metadata():
    header = model_card_header(library_name="peft")

    assert "license: other" in header
    assert "license_name: qwen-research" in header
    assert "Qwen/Qwen2.5-3B-Instruct/blob/aa8e72537993ba99e69dfaafa59ed015b17504d1/LICENSE" in header
    assert "license: apache-2.0" not in header


def test_bundled_qwen_license_matches_the_pinned_upstream_bytes():
    payload = (ROOT / "LICENSES" / "QWEN-RESEARCH-LICENSE.txt").read_bytes()

    assert hashlib.sha256(payload).hexdigest() == QWEN_LICENSE_SHA256


def test_model_card_legal_section_states_model_and_dataset_boundaries():
    section = model_card_legal_section()

    assert "Improved using Qwen" in section
    assert "非商業研究與評估" in section
    assert "GSM8K" in section
    assert "MIT" in section
    assert "Cobbe et al." in section


def test_hf_layout_accepts_a_clean_merged_and_lora_pair():
    errors = audit_hf_file_layout(
        lora_files={
            "README.md",
            "LICENSE",
            "NOTICE",
            "adapter_config.json",
            "adapter_model.safetensors",
        },
        merged_files={
            "README.md",
            "LICENSE",
            "NOTICE",
            "config.json",
            "model-00001-of-00002.safetensors",
            "model-00002-of-00002.safetensors",
            "model.safetensors.index.json",
        },
    )

    assert errors == []


def test_hf_layout_rejects_full_model_shards_in_lora_repo():
    errors = audit_hf_file_layout(
        lora_files={
            "README.md",
            "LICENSE",
            "NOTICE",
            "adapter_config.json",
            "adapter_model.safetensors",
            "model-00001-of-00002.safetensors",
            "model.safetensors.index.json",
        },
        merged_files={
            "README.md",
            "LICENSE",
            "NOTICE",
            "config.json",
            "model-00001-of-00002.safetensors",
            "model.safetensors.index.json",
        },
    )

    assert any("LoRA repo contains full-model artifact" in error for error in errors)


def test_hf_layout_rejects_nested_full_model_shards_in_lora_repo():
    errors = audit_hf_file_layout(
        lora_files={
            "README.md",
            "LICENSE",
            "NOTICE",
            "adapter_config.json",
            "adapter_model.safetensors",
            "stale/model-00001-of-00002.safetensors",
        },
        merged_files={
            "README.md",
            "LICENSE",
            "NOTICE",
            "config.json",
            "model.safetensors",
        },
    )

    assert any("stale/model-00001" in error for error in errors)
