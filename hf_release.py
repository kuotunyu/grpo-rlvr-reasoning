"""Pure helpers for licensing and auditing the Hugging Face release surface."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import PurePosixPath


QWEN_BASE_MODEL = "Qwen/Qwen2.5-3B-Instruct"
QWEN_BASE_REVISION = "aa8e72537993ba99e69dfaafa59ed015b17504d1"
QWEN_LICENSE_SHA256 = "ef52482bb785733093dc9a2e8edd8e764c77d12d8e9d8f10a80c9b547d32d0f9"
QWEN_LICENSE_URL = (
    f"https://huggingface.co/{QWEN_BASE_MODEL}/blob/{QWEN_BASE_REVISION}/LICENSE"
)
QWEN_NOTICE = (
    "Qwen is licensed under the Qwen RESEARCH LICENSE AGREEMENT, "
    "Copyright (c) Alibaba Cloud. All Rights Reserved."
)


def model_card_header(*, library_name: str) -> str:
    """Return HF metadata that preserves the upstream model-license boundary."""
    if library_name not in {"peft", "transformers"}:
        raise ValueError(f"unsupported library_name: {library_name}")
    return f"""---
license: other
license_name: qwen-research
license_link: {QWEN_LICENSE_URL}
base_model: {QWEN_BASE_MODEL}
datasets:
- openai/gsm8k
language:
- en
library_name: {library_name}
pipeline_tag: text-generation
tags:
- grpo
- rlvr
- reasoning
- unsloth
- trl
- qwen2.5
---
"""


def model_card_legal_section() -> str:
    """Return the attribution and license section shared by both model cards."""
    return f"""
> **Improved using Qwen.** 本模型由 `{QWEN_BASE_MODEL}` 經 GRPO/QLoRA
> 微調而成。

## 授權與資料來源

- **模型 artifact：** 受 [Qwen Research License]({QWEN_LICENSE_URL}) 約束，
  僅授權非商業研究與評估；商業使用需另向 Qwen/Alibaba Cloud 取得授權。
  下載或散布本模型不會取得 GitHub 原始碼的 Apache-2.0 授權。
- **GSM8K：** 訓練資料來自 OpenAI 的 GSM8K，原始資料以 MIT License 發布。
  請引用 Cobbe et al., *Training Verifiers to Solve Math Word Problems*,
  arXiv:2110.14168 (2021)。
- **原始碼：** 訓練、評測與分析程式的個別授權與第三方聲明請見 GitHub repo
  的 `LICENSE`、`LICENSES/` 與 `THIRD_PARTY_NOTICES.md`。

Redistribution notice: {QWEN_NOTICE}
"""


def model_notice() -> str:
    """Return the NOTICE content required for redistributed Qwen derivatives."""
    return f"""{QWEN_NOTICE}

Improved using Qwen.

Base model: {QWEN_BASE_MODEL}
Modification: GRPO/QLoRA fine-tuning on the GSM8K training split, with
rank-32 adapters targeting Q/K/V/O and MLP projection modules.

The model artifact is governed by the Qwen Research License Agreement.
The project source-code license does not replace or broaden that agreement.
"""


_FULL_MODEL_SHARD_RE = re.compile(r"model-\d{5}-of-\d{5}\.safetensors")
_FORBIDDEN_LORA_FILES = {"config.json", "model.safetensors.index.json"}


def audit_hf_file_layout(
    *, lora_files: Iterable[str], merged_files: Iterable[str]
) -> list[str]:
    """Return release-layout errors; an empty list means the pair is publishable."""
    lora = set(lora_files)
    merged = set(merged_files)
    errors: list[str] = []

    for filename in sorted(
        {"README.md", "LICENSE", "NOTICE", "adapter_config.json", "adapter_model.safetensors"}
        - lora
    ):
        errors.append(f"LoRA repo missing required file: {filename}")

    forbidden = sorted(
        filename
        for filename in lora
        if PurePosixPath(filename).name in _FORBIDDEN_LORA_FILES
        or PurePosixPath(filename).name == "model.safetensors"
        or _FULL_MODEL_SHARD_RE.fullmatch(PurePosixPath(filename).name)
    )
    for filename in forbidden:
        errors.append(f"LoRA repo contains full-model artifact: {filename}")

    for filename in sorted({"README.md", "LICENSE", "NOTICE", "config.json"} - merged):
        errors.append(f"Merged repo missing required file: {filename}")
    if not any(
        filename == "model.safetensors" or _FULL_MODEL_SHARD_RE.fullmatch(filename)
        for filename in merged
    ):
        errors.append("Merged repo missing model safetensors")

    return errors
