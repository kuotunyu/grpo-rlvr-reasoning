# Third-party notices and license scope

This file separates the license for original project code from the licenses
that govern adapted notebook code, dataset excerpts, and model artifacts.

## Repository code

The root [Apache License 2.0](LICENSE) applies to original code,
documentation, tests, and assets in this repository, except for the files
explicitly listed below.

`rewards.py` and `train_grpo_colab.ipynb` adapt the Unsloth
[`Qwen2.5_(3B)-GRPO.ipynb`](https://github.com/unslothai/notebooks/blob/ff0685ab2c1d604f5605ace8652aa42c1e6bb10b/nb/Qwen2.5_%283B%29-GRPO.ipynb),
which was distributed under LGPL-3.0 at the pinned upstream revision.
Those two modified files are therefore distributed under LGPL-3.0. A copy of
the upstream license is included at
[`LICENSES/UNSLOTH-NOTEBOOKS-LGPL-3.0.txt`](LICENSES/UNSLOTH-NOTEBOOKS-LGPL-3.0.txt).

The modifications include robust numeric extraction, multiline-format
matching, pure reward functions, unit tests, Drive checkpoint recovery,
JSONL logging, paired evaluation, release verification, and corrected
license metadata. The original Unsloth notebook also credits William Brown's
GRPO demonstration; this repository preserves that provenance rather than
claiming the reward layout as wholly original.

Third-party Python packages installed or imported by the project remain under
their own licenses; neither Apache-2.0 nor LGPL-3.0 relicenses those packages.

## GSM8K data included in `results/`

`results/eval_generations_base.jsonl` and
`results/eval_generations_trained.jsonl` each include the question text from
the first 200 rows of the GSM8K `main` test split. The `gold` field is a
numeric value derived from the corresponding GSM8K answer. This third-party
content is not relicensed under the repository's Apache-2.0 license.

- Source: [OpenAI grade-school-math](https://github.com/openai/grade-school-math)
- Copyright: Copyright (c) 2021 OpenAI
- License: MIT; a copy is included at
  [`LICENSES/GSM8K-MIT.txt`](LICENSES/GSM8K-MIT.txt)
- Dataset citation:

```bibtex
@article{cobbe2021gsm8k,
  title   = {Training Verifiers to Solve Math Word Problems},
  author  = {Cobbe, Karl and Kosaraju, Vineet and Bavarian, Mohammad and
             Chen, Mark and Jun, Heewoo and Kaiser, Lukasz and
             Plappert, Matthias and Tworek, Jerry and Hilton, Jacob and
             Nakano, Reiichiro and Hesse, Christopher and Schulman, John},
  journal = {arXiv preprint arXiv:2110.14168},
  year    = {2021}
}
```

The model completions in those JSONL files are generated evaluation outputs;
the embedded GSM8K questions remain subject to the notice above.

## Qwen model boundary

This GitHub repository does not contain Qwen weights. It references
`Qwen/Qwen2.5-3B-Instruct` and two fine-tuned Hugging Face artifacts. The base
model, merged weights, and LoRA adapter are governed by the
[Qwen Research License](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/aa8e72537993ba99e69dfaafa59ed015b17504d1/LICENSE),
not by this repository's Apache-2.0 license. That license limits use to
non-commercial research or evaluation unless a separate commercial license is
obtained. A verbatim copy is included at
[`LICENSES/QWEN-RESEARCH-LICENSE.txt`](LICENSES/QWEN-RESEARCH-LICENSE.txt).
The bundled bytes are pinned to Qwen revision
`aa8e72537993ba99e69dfaafa59ed015b17504d1` and SHA-256
`ef52482bb785733093dc9a2e8edd8e764c77d12d8e9d8f10a80c9b547d32d0f9`.

Required redistribution notice:

> Qwen is licensed under the Qwen RESEARCH LICENSE AGREEMENT, Copyright (c)
> Alibaba Cloud. All Rights Reserved.

The model artifacts must also display **Improved using Qwen** and include the
Qwen agreement and NOTICE when redistributed.
