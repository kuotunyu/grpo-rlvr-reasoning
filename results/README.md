# Evaluation artifact provenance

This directory preserves the committed evidence for a paired evaluation of
the base and GRPO-trained models. The reports can be recalculated without a
GPU; regenerating model completions requires the model stack and GPU described
below.

## Dataset content and license

Both `eval_generations_*.jsonl` files contain question text from the first 200
rows of the GSM8K `main` test split. That text is third-party data released by
OpenAI under the MIT License (Copyright 2021 OpenAI). See
[`../LICENSES/GSM8K-MIT.txt`](../LICENSES/GSM8K-MIT.txt), the citation in
[`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md), and the original
[dataset repository](https://github.com/openai/grade-school-math).

The repository's Apache-2.0 license does not replace the GSM8K MIT notice.

## JSONL schema

Each file has 200 rows in dataset order and the same fields:

| Field | Meaning |
|---|---|
| `idx` | Zero-based position in the selected test slice |
| `question` | GSM8K question text (third-party MIT content) |
| `gold` | Numeric final answer derived from GSM8K's answer field |
| `completion` | Model-generated response |
| `n_tokens` | Generated tokens through the first EOS |
| `strict_correct` | Correct final number inside the final `<answer>` block |
| `flexible_correct` | Correct final number anywhere in the full completion |
| `soft_format` | Reasoning and answer tags appear in order |
| `strict_format` | Completion fully matches the required tagged structure |

The base and trained files have identical `idx`, `question`, and `gold` values
at every row. The two model outputs are therefore paired observations.

## Frozen provenance

[`artifact_manifest.json`](artifact_manifest.json) records every committed
evidence file's byte size and SHA-256 plus these reconstruction pins:

- Dataset: `openai/gsm8k`, revision
  `740312add88f781978c0658806c59bc2815b9866`, `main` test rows 0–199.
- Canonical GSM8K test source: OpenAI commit
  `3101c7d5072418e28b9008a6636bde82a006892c`, file SHA-256
  `3730d312f6e3440559ace48831e51066acaca737f6eabec99bccb9e4b3c39d14`.
- Base model: `Qwen/Qwen2.5-3B-Instruct`, revision
  `aa8e72537993ba99e69dfaafa59ed015b17504d1`.
- Trained merged weights: `steven0226/qwen2.5-3b-grpo-gsm8k`, weight-complete
  revision `916d51042e6e660b2b652f1442ea32f511aa4cca`.
- Decode: greedy (`do_sample=False`), `max_new_tokens=768`, BF16, Tesla T4.

The original July 2026 evaluation did not record every installed package
version or resolved commit in its metrics JSON. The pins above were recovered
from immutable upstream and Hugging Face histories: the dataset/base revisions
were already current at run time, and the trained revision is the exact
weight-complete commit uploaded before evaluation. This is sufficient to
identify inputs, but not a promise of bit-for-bit regeneration across CUDA,
driver, PyTorch, Transformers, or tokenizer changes.

## Offline verification

```bash
python eval/verify_results.py
python eval/analyze_paired.py
python -m pytest tests -q
```

The first command checks SHA-256, file sizes, JSONL schemas, row pairing, and
aggregate metrics. The second reconstructs the paired Markdown/JSON analysis
from committed JSONL without running either model.

## Regenerating completions

`eval/run_eval.py` now pins the dataset and base model revisions above and pins
the default trained model to its weight revision. A custom model or adapter can
still be supplied explicitly:

```bash
python eval/run_eval.py \
  --trained-model steven0226/qwen2.5-3b-grpo-gsm8k \
  --trained-revision 916d51042e6e660b2b652f1442ea32f511aa4cca
```

`do_sample=False` removes sampling randomness; it does not guarantee
bit-identical GPU output across software or hardware stacks.
