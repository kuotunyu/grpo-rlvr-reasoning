# Post-release hardening design

**Date:** 2026-08-30  
**Status:** Approved direction; written specification awaiting final review  
**Repository:** `kuotunyu/grpo-rlvr-reasoning`

## Context

The GitHub repository is public, its test workflow passes, and both Hugging
Face repair pull requests are merged. The live model repositories now expose
the reviewed Qwen license metadata and artifact layouts. The remaining work is
not a publication blocker; it is intended to make the release easier to audit,
discover, and cite as a stable portfolio artifact.

The current repository has 80 offline tests and a committed evidence manifest.
It does not yet have a reusable live-release auditor, a multi-version CI
matrix, GitHub topics, or a versioned GitHub Release. One README tree comment
also still describes the already-merged Hugging Face repair as pending.

## Goals

1. Turn the manual GitHub/Hugging Face verification performed during release
   into one deterministic, read-only command.
2. Expand CI coverage without requiring a GPU or downloading model weights.
3. Remove stale publication wording and expose the audit command clearly.
4. Improve GitHub discoverability with accurate topics and a useful homepage.
5. Create a reviewed `v1.0.0` GitHub Release only after all new checks pass.

## Non-goals and constraints

- Do not retrain a model or rerun GPU evaluation in this phase.
- Do not change, delete, or rewrite either Hugging Face repository.
- Do not download multi-gigabyte model or adapter blobs in CI.
- Do not broaden the Qwen Research License or imply that model weights are
  Apache-2.0.
- Do not claim that the 200-example evaluation generalizes to the full GSM8K
  test set, other benchmarks, other seeds, or other models.
- Do not add an identity statement equating the GitHub and Hugging Face account
  names. Normal links to both published surfaces remain appropriate.
- Keep the live auditor dependency-free beyond the Python standard library and
  existing local modules so that it can run in a clean GitHub Actions runner.
- Do not touch any portfolio repository other than this GRPO project.

## Approaches considered

### A. Metadata-only polish

Fix the stale README text, set GitHub topics, and create a release. This is
fast, but it leaves the most valuable manual release checks unreproducible and
does not guard against future remote drift.

### B. No-GPU release hardening — selected

Add a tested live-release auditor, strengthen offline CI, polish README and
GitHub metadata, and create `v1.0.0` after the gates pass. This gives the best
portfolio and maintenance value without paying for another training run.

### C. Scientific expansion first

Run all 1,319 GSM8K test examples and multiple training seeds before polishing
the release. This would strengthen empirical claims, but it requires hours of
GPU time and does not address the missing operational release checks. It is
deferred until the no-GPU release is stable.

## Design

### 1. Read-only public release auditor

Create `release_audit.py` as a small command-line program with pure validation
helpers and injectable fetch functions. It will read
`docs/huggingface/remote-artifact-audit.json` as the sole record of reviewed
Hugging Face heads and artifact hashes.

The command will use `urllib.request` with an explicit user agent and timeout to
query only public endpoints:

- GitHub repository metadata for `kuotunyu/grpo-rlvr-reasoning`;
- each Hugging Face model API response with blob metadata enabled;
- each live `README.md`, `LICENSE`, and `NOTICE` at the pinned live revision.

It will verify:

- the GitHub repository is public and its default branch is `main`;
- both Hugging Face repositories are public and resolve to the recorded live
  heads;
- `hf_release.audit_hf_file_layout()` accepts the live merged/LoRA file pair;
- the two merged shards and LoRA adapter retain the recorded sizes and SHA-256
  values exposed through Hugging Face LFS metadata;
- the LoRA repository does not expose full-model shards, a model index, or a
  standalone full-model configuration;
- both cards contain the generated license header and legal section for their
  respective libraries;
- both `LICENSE` files match the pinned Qwen bytes by size and SHA-256;
- both `NOTICE` files exactly match `hf_release.model_notice()`.

The program must not download model weights. It will aggregate validation
failures, print each error with its repository/file context, and exit non-zero
when any check or network request fails. Success output will name both verified
live heads and the three retained weight artifacts.

### 2. Tests and offline gates

Add focused tests for the auditor using in-memory API/file fixtures rather than
network calls. The tests will cover the success path and at least these failure
classes:

- remote head drift;
- missing or stale LoRA artifacts;
- altered LFS hash or size;
- incorrect card license metadata;
- altered Qwen license or notice;
- malformed/unreachable endpoint translated into a concise audit error.

Add lightweight repository-health tests that:

- parse `train_grpo_colab.ipynb` as JSON and confirm it contains no stored
  outputs;
- verify every local Markdown link target exists;
- reject the stale pre-merge wording in README and Hugging Face audit docs.

The existing 80 tests and `eval/verify_results.py` remain authoritative. No
test may mutate committed result artifacts.

### 3. GitHub Actions

Update `.github/workflows/ci.yml` to test Python 3.10, 3.11, and 3.12. Each
matrix job will install `pytest`, run the complete test suite, run
`eval/verify_results.py`, and byte-compile the Python sources. These are all
offline checks.

Create `.github/workflows/release-audit.yml` for the live network audit. It will
run on manual dispatch, weekly schedule, and changes to the auditor, release
metadata, or Hugging Face audit record on `main`. It will use read-only
permissions and execute `python release_audit.py`. Keeping this separate from
the offline matrix makes network outages identifiable without obscuring source
test failures.

### 4. README and release documentation

Update README to:

- replace the stale “pending Hugging Face repair” tree comment with the live,
  post-merge audit description;
- add badges for the offline test workflow and public-release audit;
- document `python release_audit.py` next to the existing offline verification
  commands;
- retain all current licensing and empirical-claim caveats.

Create `docs/releases/v1.0.0.md` as the GitHub Release notes source. It will
summarize the training/evaluation evidence, link both Hugging Face artifacts,
state the Qwen/GSM8K license boundaries, identify the 200-example evaluation
scope, and list the reproducibility commands. It will not introduce stronger
claims than README or the paired analysis.

### 5. GitHub metadata and `v1.0.0`

After code and documentation are merged to `main` and all workflows succeed:

- set the repository homepage to the merged Hugging Face model;
- set focused topics: `grpo`, `rlvr`, `qwen`, `gsm8k`,
  `reinforcement-learning`, `llm`, and `reasoning`;
- create GitHub Release `v1.0.0` targeting the verified `main` commit, using
  `docs/releases/v1.0.0.md` verbatim as its notes;
- rerun the live auditor and confirm the release page is public.

The tag and release are created only once. If a pre-release check fails, no tag
is created. Later corrections use a new normal commit and patch release rather
than rewriting `v1.0.0` history.

## Error handling and rollback

- Network operations are read-only until the final GitHub metadata/release
  step and have bounded timeouts.
- A changed HF live head is treated as drift requiring review, not automatically
  accepted by rewriting the audit record.
- GitHub metadata changes are reversible through normal repository settings.
- The release tag is created only after final verification; it is not created
  speculatively and will not be force-moved.
- No Hugging Face write is part of this design.

## Acceptance criteria

1. All existing and new tests pass on Python 3.10, 3.11, and 3.12.
2. `python eval/verify_results.py` passes in every offline CI matrix job.
3. `python release_audit.py` passes against both live HF default branches
   without downloading model weights.
4. README contains no stale pre-merge status and documents both verification
   commands.
5. Offline CI and the separate public-release workflow both complete
   successfully on the final `main` commit.
6. The repository has the selected topics, merged-model homepage, and a public
   immutable `v1.0.0` release.
7. The final worktree is clean and local, origin, and GitHub `main` point to the
   same commit.

## Estimated effort

- Auditor and unit tests: 2–4 hours.
- CI and repository-health tests: 1–2 hours.
- README, release notes, and GitHub metadata: 45–90 minutes.
- Final workflow and release verification: 30–60 minutes.

Total expected elapsed work: approximately 4–7 hours, with no GPU requirement.
