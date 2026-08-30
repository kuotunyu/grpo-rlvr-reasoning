"""Read-only audit of the public GitHub and Hugging Face release surfaces."""

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


FetchJson = Callable[[str], dict[str, Any]]
FetchBytes = Callable[[str], bytes]
ROOT = Path(__file__).resolve().parent
DEFAULT_AUDIT_PATH = ROOT / "docs" / "huggingface" / "remote-artifact-audit.json"
GITHUB_API_URL = "https://api.github.com/repos/kuotunyu/grpo-rlvr-reasoning"
HF_API_TEMPLATE = "https://huggingface.co/api/models/{repo_id}?blobs=true"
HF_FILE_TEMPLATE = (
    "https://huggingface.co/{repo_id}/resolve/{revision}/{filename}"
)
REQUIRED_ARTIFACTS = {
    "merged": (
        "artifacts",
        (
            "model-00001-of-00002.safetensors",
            "model-00002-of-00002.safetensors",
        ),
    ),
    "lora": ("adapter", ("adapter_model.safetensors",)),
}


def _request(url: str, timeout: float) -> bytes:
    headers = {"User-Agent": "grpo-rlvr-release-audit/1.0"}
    if url.startswith("https://api.github.com/") and os.environ.get(
        "GITHUB_TOKEN"
    ):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise OSError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise OSError(str(exc.reason)) from exc


def http_get_bytes(url: str, timeout: float = 15.0) -> bytes:
    return _request(url, timeout)


def http_get_json(url: str, timeout: float = 15.0) -> dict[str, Any]:
    value = json.loads(_request(url, timeout).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _safe_fetch(
    label: str,
    url: str,
    fetch: Callable[[str], Any],
    errors: list[str],
) -> Any | None:
    try:
        return fetch(url)
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: unable to fetch {url}: {exc}")
        return None


def _artifact_records(repo_record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source = (
        repo_record.get("artifacts", {})
        if "artifacts" in repo_record
        else repo_record.get("adapter", {})
    )
    return {
        name: metadata
        for name, metadata in source.items()
        if isinstance(metadata, dict)
        and "sha256" in metadata
        and "size" in metadata
    }


def _validate_audit_record(record: Any) -> list[str]:
    if not isinstance(record, dict):
        return ["audit record: root must be a JSON object"]
    repositories = record.get("repositories")
    if not isinstance(repositories, dict):
        return ["audit record: missing repositories object"]
    errors = []
    for kind in ("merged", "lora"):
        repo = repositories.get(kind)
        if not isinstance(repo, dict):
            errors.append(f"audit record: missing repositories.{kind} object")
            continue
        for field in ("repo_id", "live_head"):
            if not isinstance(repo.get(field), str) or not repo[field]:
                errors.append(
                    f"audit record: repositories.{kind}.{field} "
                    "must be a non-empty string"
                )
        collection, required_artifacts = REQUIRED_ARTIFACTS[kind]
        artifact_records = repo.get(collection)
        if not isinstance(artifact_records, dict):
            errors.append(
                f"audit record: repositories.{kind}.{collection} "
                "must be an object"
            )
            continue
        for name in required_artifacts:
            prefix = f"audit record: repositories.{kind}.{collection}.{name}"
            if name not in artifact_records:
                errors.append(f"{prefix} is required")
                continue
            metadata = artifact_records[name]
            if not isinstance(metadata, dict):
                errors.append(f"{prefix} must be an object")
                continue
            size = metadata.get("size")
            if type(size) is not int or size <= 0:
                errors.append(f"{prefix}.size must be a positive integer")
            sha256 = metadata.get("sha256")
            if not (
                isinstance(sha256, str)
                and len(sha256) == 64
                and all(character in "0123456789abcdefABCDEF" for character in sha256)
            ):
                errors.append(
                    f"{prefix}.sha256 must be 64 hexadecimal characters"
                )
    return errors


def audit_public_release(
    record: dict[str, Any],
    fetch_json: FetchJson,
    fetch_bytes: FetchBytes,
) -> list[str]:
    """Return live-release errors without downloading any model weight blob."""
    errors = _validate_audit_record(record)
    if errors:
        return errors
    github = _safe_fetch("GitHub", GITHUB_API_URL, fetch_json, errors)
    if github is not None:
        if github.get("private") is not False:
            errors.append("GitHub: repository is not public")
        if github.get("default_branch") != "main":
            errors.append("GitHub: default branch is not main")
    repo_files: dict[str, set[str]] = {}
    for kind, library in (("merged", "transformers"), ("lora", "peft")):
        repo = record["repositories"][kind]
        repo_id = repo["repo_id"]
        api_url = HF_API_TEMPLATE.format(repo_id=repo_id)
        payload = _safe_fetch(repo_id, api_url, fetch_json, errors)
        if payload is None:
            continue
        if payload.get("private") is not False:
            errors.append(f"{repo_id}: repository is not public")
        if payload.get("gated") is not False:
            errors.append(f"{repo_id}: repository requires gated access")
        if payload.get("disabled") is not False:
            errors.append(f"{repo_id}: repository is disabled")
        if payload.get("sha") != repo["live_head"]:
            errors.append(
                f"{repo_id}: live head drifted: "
                f"{payload.get('sha')!r} != {repo['live_head']!r}"
            )
        siblings_raw = payload.get("siblings")
        if not isinstance(siblings_raw, list):
            errors.append(f"{repo_id}: siblings must be a list")
            continue
        siblings: dict[str, dict[str, Any]] = {}
        invalid_siblings = False
        for index, item in enumerate(siblings_raw):
            if not isinstance(item, dict):
                errors.append(f"{repo_id}: sibling {index} must be an object")
                invalid_siblings = True
                continue
            name = item.get("rfilename")
            if not isinstance(name, str) or not name:
                errors.append(
                    f"{repo_id}: sibling {index} has invalid rfilename"
                )
                invalid_siblings = True
                continue
            siblings[name] = item
        if invalid_siblings:
            continue
        repo_files[kind] = set(siblings)
        for name, expected in _artifact_records(repo).items():
            actual = siblings.get(name)
            if actual is None:
                errors.append(f"{repo_id}: missing retained artifact {name}")
                continue
            if actual.get("size") != expected["size"]:
                errors.append(f"{repo_id}/{name}: size mismatch")
            lfs = actual.get("lfs")
            if not isinstance(lfs, dict):
                errors.append(
                    f"{repo_id}/{name}: lfs metadata must be an object"
                )
            elif lfs.get("sha256") != expected["sha256"]:
                errors.append(f"{repo_id}/{name}: SHA-256 mismatch")
        card_url = HF_FILE_TEMPLATE.format(
            repo_id=repo_id,
            revision=repo["live_head"],
            filename="README.md",
        )
        card_bytes = _safe_fetch(
            f"{repo_id}/README.md", card_url, fetch_bytes, errors
        )
        if card_bytes is not None:
            try:
                card = card_bytes.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(f"{repo_id}/README.md: invalid UTF-8")
            else:
                if not card.startswith(model_card_header(library_name=library)):
                    errors.append(
                        f"{repo_id}/README.md: generated license header mismatch"
                    )
                if model_card_legal_section() not in card:
                    errors.append(
                        f"{repo_id}/README.md: generated legal section missing"
                    )
        license_url = HF_FILE_TEMPLATE.format(
            repo_id=repo_id,
            revision=repo["live_head"],
            filename="LICENSE",
        )
        license_bytes = _safe_fetch(
            f"{repo_id}/LICENSE", license_url, fetch_bytes, errors
        )
        if license_bytes is not None:
            if len(license_bytes) != 7388:
                errors.append(f"{repo_id}/LICENSE: size mismatch")
            if hashlib.sha256(license_bytes).hexdigest() != QWEN_LICENSE_SHA256:
                errors.append(f"{repo_id}/LICENSE: SHA-256 mismatch")
        notice_url = HF_FILE_TEMPLATE.format(
            repo_id=repo_id,
            revision=repo["live_head"],
            filename="NOTICE",
        )
        notice_bytes = _safe_fetch(
            f"{repo_id}/NOTICE", notice_url, fetch_bytes, errors
        )
        if notice_bytes is not None and notice_bytes != model_notice().encode("utf-8"):
            errors.append(f"{repo_id}/NOTICE: generated notice mismatch")
    if set(repo_files) == {"merged", "lora"}:
        errors.extend(
            audit_hf_file_layout(
                lora_files=repo_files["lora"],
                merged_files=repo_files["merged"],
            )
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit the live public GitHub/Hugging Face release"
    )
    parser.add_argument(
        "--audit-record", type=Path, default=DEFAULT_AUDIT_PATH
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)
    try:
        record = json.loads(args.audit_record.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
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
        for name, metadata in _artifact_records(
            record["repositories"][kind]
        ).items():
            print(
                f"verified {name}: {metadata['size']} bytes, "
                f"sha256={metadata['sha256']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
