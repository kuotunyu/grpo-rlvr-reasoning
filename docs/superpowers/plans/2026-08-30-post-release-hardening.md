# Post-release Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible no-GPU public-release audit, strengthen offline CI, polish repository metadata, and publish a verified `v1.0.0` GitHub Release.

**Architecture:** Keep release policy in the existing `hf_release.py` and committed remote facts in `docs/huggingface/remote-artifact-audit.json`. Add one dependency-free `release_audit.py` adapter that fetches public GitHub/Hugging Face metadata and small legal/card files, then applies pure validations. Keep network checks in a separate workflow from the Python-version offline test matrix.

**Tech Stack:** Python 3.10–3.12 standard library, pytest, GitHub Actions, GitHub CLI, Hugging Face public REST endpoints.

## Global Constraints

- Do not retrain or rerun GPU evaluation in this phase.
- Do not modify, delete, or rewrite either Hugging Face repository.
- Never download model or adapter weight blobs during the audit.
- Preserve the Qwen Research License boundary and the GSM8K MIT attribution.
- Preserve the existing 200-example evaluation caveat and avoid stronger claims.
- Do not add an identity statement equating the GitHub and Hugging Face account names.
- Keep `release_audit.py` free of third-party runtime dependencies.
- Touch only `D:\AI-Portfolio\CC_github部隊\RL_Github\1_GRPORLVR_推理訓練` and its GitHub repository.
- Implement feature and bug behavior test-first, commit each independently reviewable task, and do not create `v1.0.0` until all final workflows pass.

---

### Task 1: Dependency-free public release auditor

**Files:**
- Create: `release_audit.py`
- Create: `tests/test_release_audit.py`
- Read: `hf_release.py`
- Read: `docs/huggingface/remote-artifact-audit.json`

**Interfaces:**
- Consumes: `hf_release.QWEN_LICENSE_SHA256`, `model_card_header()`, `model_card_legal_section()`, `model_notice()`, and `audit_hf_file_layout()`.
- Produces: `audit_public_release(record, fetch_json, fetch_bytes) -> list[str]`, `http_get_json(url, timeout=15.0) -> dict[str, object]`, `http_get_bytes(url, timeout=15.0) -> bytes`, and CLI `main(argv=None) -> int`.
- `fetch_json` and `fetch_bytes` accept one URL and return decoded JSON / raw bytes; tests inject dictionary-backed implementations.

- [ ] **Step 1: Create a valid in-memory remote fixture and the first failing success-path test**

Create `tests/test_release_audit.py` with helpers that load the real audit record and construct responses containing only required files:

```python
import copy
import json
from pathlib import Path

from hf_release import model_card_header, model_card_legal_section, model_notice
from release_audit import audit_public_release

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "docs" / "huggingface" / "remote-artifact-audit.json"


def load_record():
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def make_remote_fixture():
    record = load_record()
    responses_json = {
        "https://api.github.com/repos/kuotunyu/grpo-rlvr-reasoning": {
            "private": False,
            "default_branch": "main",
        }
    }
    responses_bytes = {}
    required = {
        "merged": ("transformers", ["config.json", "model.safetensors.index.json"]),
        "lora": ("peft", ["adapter_config.json"]),
    }
    for kind, (library, ordinary_files) in required.items():
        repo = record["repositories"][kind]
        repo_id = repo["repo_id"]
        head = repo["live_head"]
        siblings = [{"rfilename": name} for name in ordinary_files]
        for name, metadata in (
            repo.get("artifacts", {}) | repo.get("adapter", {})
        ).items():
            if not isinstance(metadata, dict) or "sha256" not in metadata:
                continue
            siblings.append({
                "rfilename": name,
                "size": metadata["size"],
                "lfs": {"sha256": metadata["sha256"]},
            })
        siblings.extend({"rfilename": name} for name in ("README.md", "LICENSE", "NOTICE"))
        responses_json[f"https://huggingface.co/api/models/{repo_id}?blobs=true"] = {
            "private": False,
            "sha": head,
            "siblings": siblings,
        }
        base = f"https://huggingface.co/{repo_id}/resolve/{head}"
        responses_bytes[f"{base}/README.md"] = (
            model_card_header(library_name=library) + "\nModel details\n" + model_card_legal_section()
        ).encode()
        responses_bytes[f"{base}/LICENSE"] = (
            ROOT / "LICENSES" / "QWEN-RESEARCH-LICENSE.txt"
        ).read_bytes()
        responses_bytes[f"{base}/NOTICE"] = model_notice().encode()
    return record, responses_json, responses_bytes


def test_audit_accepts_reviewed_public_release():
    record, json_map, bytes_map = make_remote_fixture()
    errors = audit_public_release(record, json_map.__getitem__, bytes_map.__getitem__)
    assert errors == []
```

- [ ] **Step 2: Run the test and confirm the missing-module failure**

Run: `python -m pytest tests/test_release_audit.py::test_audit_accepts_reviewed_public_release -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'release_audit'`.

- [ ] **Step 3: Implement the minimal audit data flow**

Create `release_audit.py` with constants and helpers:

```python
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from hf_release import (
    QWEN_LICENSE_SHA256,
    audit_hf_file_layout,
    model_card_header,
    model_card_legal_section,
    model_notice,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_AUDIT_PATH = ROOT / "docs" / "huggingface" / "remote-artifact-audit.json"
GITHUB_API_URL = "https://api.github.com/repos/kuotunyu/grpo-rlvr-reasoning"
HF_API_TEMPLATE = "https://huggingface.co/api/models/{repo_id}?blobs=true"
HF_FILE_TEMPLATE = "https://huggingface.co/{repo_id}/resolve/{revision}/{filename}"
FetchJson = Callable[[str], dict[str, Any]]
FetchBytes = Callable[[str], bytes]


def _safe_fetch(label, url, fetch, errors):
    try:
        return fetch(url)
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: unable to fetch {url}: {exc}")
        return None


def _artifact_records(repo_record):
    source = repo_record.get("artifacts", {}) if "artifacts" in repo_record else repo_record.get("adapter", {})
    return {
        name: metadata
        for name, metadata in source.items()
        if isinstance(metadata, dict) and "sha256" in metadata and "size" in metadata
    }


def audit_public_release(record, fetch_json, fetch_bytes):
    errors = []
    github = _safe_fetch("GitHub", GITHUB_API_URL, fetch_json, errors)
    if github is not None:
        if github.get("private") is not False:
            errors.append("GitHub: repository is not public")
        if github.get("default_branch") != "main":
            errors.append("GitHub: default branch is not main")

    repo_files = {}
    for kind, library in (("merged", "transformers"), ("lora", "peft")):
        repo = record["repositories"][kind]
        repo_id, head = repo["repo_id"], repo["live_head"]
        api_url = HF_API_TEMPLATE.format(repo_id=repo_id)
        payload = _safe_fetch(repo_id, api_url, fetch_json, errors)
        if payload is None:
            continue
        if payload.get("private") is not False:
            errors.append(f"{repo_id}: repository is not public")
        if payload.get("sha") != head:
            errors.append(f"{repo_id}: live head drifted: {payload.get('sha')!r} != {head!r}")
        siblings = {item.get("rfilename"): item for item in payload.get("siblings", [])}
        repo_files[kind] = set(siblings)
        for name, expected in _artifact_records(repo).items():
            actual = siblings.get(name)
            if actual is None:
                errors.append(f"{repo_id}: missing retained artifact {name}")
                continue
            if actual.get("size") != expected["size"]:
                errors.append(f"{repo_id}/{name}: size mismatch")
            if (actual.get("lfs") or {}).get("sha256") != expected["sha256"]:
                errors.append(f"{repo_id}/{name}: SHA-256 mismatch")
        base = HF_FILE_TEMPLATE.format(repo_id=repo_id, revision=head, filename="{filename}")
        card = _safe_fetch(f"{repo_id}/README.md", base.format(filename="README.md"), fetch_bytes, errors)
        license_bytes = _safe_fetch(f"{repo_id}/LICENSE", base.format(filename="LICENSE"), fetch_bytes, errors)
        notice = _safe_fetch(f"{repo_id}/NOTICE", base.format(filename="NOTICE"), fetch_bytes, errors)
        if card is not None:
            text = card.decode("utf-8")
            if not text.startswith(model_card_header(library_name=library)):
                errors.append(f"{repo_id}/README.md: generated license header mismatch")
            if model_card_legal_section() not in text:
                errors.append(f"{repo_id}/README.md: generated legal section missing")
        if license_bytes is not None:
            if len(license_bytes) != 7388:
                errors.append(f"{repo_id}/LICENSE: size mismatch")
            if hashlib.sha256(license_bytes).hexdigest() != QWEN_LICENSE_SHA256:
                errors.append(f"{repo_id}/LICENSE: SHA-256 mismatch")
        if notice is not None and notice != model_notice().encode("utf-8"):
            errors.append(f"{repo_id}/NOTICE: generated notice mismatch")

    if set(repo_files) == {"merged", "lora"}:
        errors.extend(audit_hf_file_layout(
            lora_files=repo_files["lora"], merged_files=repo_files["merged"]
        ))
    return errors
```

Adjust only syntax/type details required by Python 3.10 while preserving these interfaces and validations.

- [ ] **Step 4: Run the success-path test**

Run: `python -m pytest tests/test_release_audit.py::test_audit_accepts_reviewed_public_release -q`

Expected: `1 passed`.

- [ ] **Step 5: Add failing mutation tests for every required failure class**

Add tests that mutate a deep-copied fixture and assert contextual errors:

```python
def test_audit_rejects_hf_head_drift():
    record, json_map, bytes_map = make_remote_fixture()
    repo_id = record["repositories"]["merged"]["repo_id"]
    json_map[f"https://huggingface.co/api/models/{repo_id}?blobs=true"]["sha"] = "changed"
    errors = audit_public_release(record, json_map.__getitem__, bytes_map.__getitem__)
    assert any("live head drifted" in error for error in errors)


def test_audit_rejects_stale_full_model_file_in_lora():
    record, json_map, bytes_map = make_remote_fixture()
    repo_id = record["repositories"]["lora"]["repo_id"]
    json_map[f"https://huggingface.co/api/models/{repo_id}?blobs=true"]["siblings"].append(
        {"rfilename": "model-00001-of-00002.safetensors"}
    )
    errors = audit_public_release(record, json_map.__getitem__, bytes_map.__getitem__)
    assert any("LoRA repo contains full-model artifact" in error for error in errors)


def test_audit_rejects_changed_artifact_hash_and_size():
    record, json_map, bytes_map = make_remote_fixture()
    repo_id = record["repositories"]["merged"]["repo_id"]
    artifact = next(
        item for item in json_map[f"https://huggingface.co/api/models/{repo_id}?blobs=true"]["siblings"]
        if item["rfilename"].endswith("safetensors")
    )
    artifact["size"] = 1
    artifact["lfs"]["sha256"] = "0" * 64
    errors = audit_public_release(record, json_map.__getitem__, bytes_map.__getitem__)
    assert any("size mismatch" in error for error in errors)
    assert any("SHA-256 mismatch" in error for error in errors)


def test_audit_rejects_changed_card_license_and_notice():
    record, json_map, bytes_map = make_remote_fixture()
    repo = record["repositories"]["lora"]
    base = f"https://huggingface.co/{repo['repo_id']}/resolve/{repo['live_head']}"
    bytes_map[f"{base}/README.md"] = b"---\nlicense: apache-2.0\n---\n"
    bytes_map[f"{base}/LICENSE"] = b"changed"
    bytes_map[f"{base}/NOTICE"] = b"changed"
    errors = audit_public_release(record, json_map.__getitem__, bytes_map.__getitem__)
    assert any("license header mismatch" in error for error in errors)
    assert any("LICENSE: SHA-256 mismatch" in error for error in errors)
    assert any("NOTICE: generated notice mismatch" in error for error in errors)


def test_audit_reports_network_failure_without_traceback():
    record, json_map, bytes_map = make_remote_fixture()
    def fail(_url):
        raise OSError("offline")
    errors = audit_public_release(record, fail, bytes_map.__getitem__)
    assert errors
    assert all("Traceback" not in error for error in errors)
    assert any("unable to fetch" in error for error in errors)
```

- [ ] **Step 6: Run mutation tests and confirm the expected failures**

Run: `python -m pytest tests/test_release_audit.py -q`

Expected: new tests fail until missing key guards, contextual messages, and layout checks are complete.

- [ ] **Step 7: Complete network transport and CLI behavior**

Add these behaviors to `release_audit.py`:

```python
def _request(url, timeout):
    headers = {"User-Agent": "grpo-rlvr-release-audit/1.0"}
    if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise OSError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise OSError(str(exc.reason)) from exc


def http_get_bytes(url, timeout=15.0):
    return _request(url, timeout)


def http_get_json(url, timeout=15.0):
    value = json.loads(_request(url, timeout).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit the live public GitHub/Hugging Face release")
    parser.add_argument("--audit-record", type=Path, default=DEFAULT_AUDIT_PATH)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)
    try:
        record = json.loads(args.audit_record.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: unable to read audit record: {exc}", file=sys.stderr)
        return 1
    errors = audit_public_release(
        record,
        lambda url: http_get_json(url, args.timeout),
        lambda url: http_get_bytes(url, args.timeout),
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    for kind in ("merged", "lora"):
        repo = record["repositories"][kind]
        print(f"verified {repo['repo_id']} @ {repo['live_head']}")
    for kind in ("merged", "lora"):
        for name, metadata in _artifact_records(record["repositories"][kind]).items():
            print(f"verified {name}: {metadata['size']} bytes, sha256={metadata['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Add a CLI test using `monkeypatch` to replace `http_get_json`/`http_get_bytes`, then assert `main([]) == 0` and the captured output includes both live heads.

- [ ] **Step 8: Run Task 1 verification**

Run:

```powershell
python -m pytest tests/test_release_audit.py -q
python release_audit.py
python -m pytest tests -q
git diff --check
```

Expected: release audit passes live without downloading weight blobs; all tests pass; no whitespace errors.

- [ ] **Step 9: Commit Task 1**

```powershell
git add -- release_audit.py tests/test_release_audit.py
git commit -m "feat: add public release auditor"
```

---

### Task 2: Repository-health tests and offline CI matrix

**Files:**
- Create: `tests/test_repository_health.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: repository Markdown and `train_grpo_colab.ipynb` as data.
- Produces: offline repository invariants enforced by pytest and Python 3.10–3.12 CI jobs.

- [ ] **Step 1: Write failing repository-health tests**

Create `tests/test_repository_health.py`:

```python
import json
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def test_notebook_is_valid_json_without_stored_outputs():
    notebook = json.loads((ROOT / "train_grpo_colab.ipynb").read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    outputs = [output for cell in notebook["cells"] for output in cell.get("outputs", [])]
    assert outputs == []


def test_local_markdown_links_exist():
    missing = []
    pattern = re.compile(r"!?\[[^]]*\]\(([^)]+)\)")
    for markdown in ROOT.rglob("*.md"):
        for raw_target in pattern.findall(markdown.read_text(encoding="utf-8")):
            target = raw_target.strip().split()[0].strip("<>")
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path_text = unquote(target.split("#", 1)[0])
            if path_text and not (markdown.parent / path_text).resolve().exists():
                missing.append(f"{markdown.relative_to(ROOT)} -> {target}")
    assert missing == []


def test_release_docs_contain_no_stale_pre_merge_status():
    checked = [
        ROOT / "README.md",
        ROOT / "docs" / "huggingface" / "REMOTE_REPAIR_PLAN.md",
        ROOT / "docs" / "huggingface" / "remote-artifact-audit.json",
    ]
    forbidden = (
        "唯讀 artifact audit 與待審的 HF 遠端修復方案",
        "NO-GO for merging the HF repairs",
        '"status": "open"',
        '"merged": false',
    )
    for path in checked:
        text = path.read_text(encoding="utf-8")
        assert not any(phrase in text for phrase in forbidden), path
```

- [ ] **Step 2: Run the stale-status test and confirm it fails on README**

Run: `python -m pytest tests/test_repository_health.py -q`

Expected: the stale-status test fails because README still contains the pending-repair tree comment; the notebook and link tests pass.

- [ ] **Step 3: Fix README status and document both auditors**

In README:

- add these badges immediately below the title:

```markdown
[![tests](https://github.com/kuotunyu/grpo-rlvr-reasoning/actions/workflows/ci.yml/badge.svg)](https://github.com/kuotunyu/grpo-rlvr-reasoning/actions/workflows/ci.yml)
[![public release audit](https://github.com/kuotunyu/grpo-rlvr-reasoning/actions/workflows/release-audit.yml/badge.svg)](https://github.com/kuotunyu/grpo-rlvr-reasoning/actions/workflows/release-audit.yml)
```

- add `python release_audit.py      # 唯讀檢查 GitHub/HF live 發布面，不下載權重` after `eval/verify_results.py` in the local verification block;
- replace `docs/huggingface/ # 唯讀 artifact audit 與待審的 HF 遠端修復方案` with `docs/huggingface/ # HF artifact audit、merged PR 與 live 驗證紀錄`.

- [ ] **Step 4: Expand offline CI to a three-version matrix**

Replace `.github/workflows/ci.yml` with:

```yaml
name: tests

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  pytest:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - run: python -m pip install --upgrade pip pytest
      - run: python -m pytest tests -q
      - run: python eval/verify_results.py
      - run: python -m compileall -q rewards.py hf_release.py release_audit.py eval tests
```

- [ ] **Step 5: Run Task 2 verification**

Run:

```powershell
python -m pytest tests/test_repository_health.py -q
python -m pytest tests -q
python eval/verify_results.py
python -m compileall -q rewards.py hf_release.py release_audit.py eval tests
git diff --check
```

Expected: all tests and verification commands pass.

- [ ] **Step 6: Commit Task 2**

```powershell
git add -- tests/test_repository_health.py .github/workflows/ci.yml README.md
git commit -m "ci: strengthen offline release gates"
```

---

### Task 3: Dedicated live-audit workflow and release notes

**Files:**
- Create: `.github/workflows/release-audit.yml`
- Create: `docs/releases/v1.0.0.md`
- Modify: `README.md` only if the workflow badge/link differs from the final workflow filename.

**Interfaces:**
- Consumes: `release_audit.py` and the committed HF audit JSON.
- Produces: a read-only scheduled/manual GitHub Actions workflow and the exact public release notes.

- [ ] **Step 1: Add the dedicated workflow**

Create `.github/workflows/release-audit.yml`:

```yaml
name: public release audit

on:
  workflow_dispatch:
  schedule:
    - cron: "17 4 * * 1"
  push:
    branches: [main]
    paths:
      - release_audit.py
      - hf_release.py
      - docs/huggingface/**
      - docs/releases/**
      - .github/workflows/release-audit.yml

permissions:
  contents: read

jobs:
  audit:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    env:
      GITHUB_TOKEN: ${{ github.token }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python release_audit.py
```

- [ ] **Step 2: Create exact `v1.0.0` release notes**

Create `docs/releases/v1.0.0.md` with this content:

```markdown
# v1.0.0 — audited public release

This is the first versioned public release of the GRPO/RLVR reasoning training
portfolio project.

## Highlights

- GRPO/QLoRA fine-tuning of `Qwen/Qwen2.5-3B-Instruct` on the GSM8K train split.
- Same-example paired evaluation on the first 200 GSM8K test problems.
- Strict accuracy: 70.5% → 79.0% (exact paired McNemar p=0.0046).
- Strict format adherence: 19.5% → 90.0%.
- Flexible accuracy: 76.0% → 79.5%; this difference was not statistically significant (p=0.2478).
- Per-example outputs, artifact hashes, paired statistics, and a dependency-free public-release audit are included.

## Model artifacts

- Merged model: https://huggingface.co/steven0226/qwen2.5-3b-grpo-gsm8k
- LoRA adapter: https://huggingface.co/steven0226/qwen2.5-3b-grpo-gsm8k-lora

The base model, merged weights, and LoRA adapter are governed by the Qwen
Research License and are limited to non-commercial research/evaluation unless
a separate commercial license is obtained. GitHub's Apache-2.0 source license
does not replace or broaden the model license.

The committed JSONL files include GSM8K question text released by OpenAI under
MIT. See `THIRD_PARTY_NOTICES.md` and `LICENSES/` for exact scope and citation.

## Verify without a GPU

```bash
python -m pytest tests -q
python eval/verify_results.py
python release_audit.py
```

The existing July 2026 generations are auditable and their statistics are
recomputable, but the original run did not capture every CUDA and package
version needed to promise bit-for-bit regeneration across environments.
```

- [ ] **Step 3: Verify workflow syntax, links, and live audit**

Run:

```powershell
python -c "import pathlib; import yaml"  # run only if PyYAML is already available
python -m pytest tests -q
python eval/verify_results.py
python release_audit.py
git diff --check
```

If PyYAML is unavailable, inspect the 26-line workflow directly and rely on the GitHub Actions parser after push; do not add PyYAML as a project dependency solely for this check.

- [ ] **Step 4: Commit Task 3**

```powershell
git add -- .github/workflows/release-audit.yml docs/releases/v1.0.0.md README.md
git commit -m "docs: prepare audited v1 release"
```

---

### Task 4: Integrate, publish metadata, and create the immutable release

**Files:**
- No new source file.
- Remote GitHub metadata: homepage, topics, workflows, tag, and Release.

**Interfaces:**
- Consumes: all prior task commits and `docs/releases/v1.0.0.md`.
- Produces: final public `main`, successful workflows, repository metadata, tag `v1.0.0`, and GitHub Release.

- [ ] **Step 1: Run the complete pre-integration verification**

Run:

```powershell
python -m pytest tests -q
python eval/verify_results.py
python release_audit.py
python -m compileall -q rewards.py hf_release.py release_audit.py eval tests
python -m json.tool docs/huggingface/remote-artifact-audit.json > $null
git diff --check
git status --short --branch
```

Expected: every command passes and the feature worktree is clean after its task commits.

- [ ] **Step 2: Integrate the feature branch into local `main` without rewriting history**

Use the `finishing-a-development-branch` skill. Because the user already authorized publication, select its local-merge option, update local `main` by fast-forward or normal merge, and rerun the complete test suite on integrated `main`. Never force-push.

- [ ] **Step 3: Push `main` and wait for both workflows**

```powershell
git push origin main
$sha = git rev-parse HEAD
gh run list --commit $sha --limit 10 --json databaseId,workflowName,status,conclusion,url,headSha
```

Wait conditionally until the `tests` workflow has three successful matrix jobs and `public release audit` concludes successfully for the exact full SHA. Diagnose any failure before proceeding; do not create a release while a gate is failing.

- [ ] **Step 4: Set GitHub homepage and topics**

```powershell
gh repo edit kuotunyu/grpo-rlvr-reasoning --homepage "https://huggingface.co/steven0226/qwen2.5-3b-grpo-gsm8k" --add-topic grpo --add-topic rlvr --add-topic qwen --add-topic gsm8k --add-topic reinforcement-learning --add-topic llm --add-topic reasoning
gh repo view kuotunyu/grpo-rlvr-reasoning --json homepageUrl,repositoryTopics,url
```

Expected: homepage is the merged model and the seven selected topics are present.

- [ ] **Step 5: Recheck tag absence and create `v1.0.0`**

```powershell
if (git tag --list v1.0.0) { throw 'v1.0.0 already exists; stop for audit' }
gh release create v1.0.0 --repo kuotunyu/grpo-rlvr-reasoning --target (git rev-parse HEAD) --title "v1.0.0 — audited public release" --notes-file docs/releases/v1.0.0.md
```

Expected: GitHub returns a public release URL and creates the tag at the verified full SHA.

- [ ] **Step 6: Perform final public-state verification**

Run:

```powershell
git fetch origin main --tags
python release_audit.py
python -m pytest tests -q
python eval/verify_results.py
$local = git rev-parse HEAD
$origin = git rev-parse origin/main
$github = gh api repos/kuotunyu/grpo-rlvr-reasoning/commits/main --jq .sha
$tag = git rev-list -n 1 v1.0.0
gh release view v1.0.0 --repo kuotunyu/grpo-rlvr-reasoning --json url,isDraft,isPrerelease,tagName,targetCommitish
git status --short --branch
```

Acceptance: local/origin/GitHub main and `v1.0.0` all resolve to the same verified commit; the Release is public, not draft/prerelease; both HF live audits and offline evidence verification pass; worktree is clean.

---

## Plan self-review map

- Auditor and no-weight network boundary: Task 1.
- Required negative tests and concise network errors: Task 1 Steps 5–8.
- Notebook, Markdown, stale-status gates: Task 2.
- Python 3.10–3.12 offline CI: Task 2.
- Separate manual/scheduled live workflow: Task 3.
- README badges/status/audit command: Task 2.
- Exact release notes and license/evidence caveats: Task 3.
- Homepage, seven topics, immutable `v1.0.0`, final verification: Task 4.
