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


def audit_public_release(
    record: dict[str, Any],
    fetch_json: FetchJson,
    fetch_bytes: FetchBytes,
) -> list[str]:
    """Return live-release errors without downloading any model weight blob."""
    errors: list[str] = []
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
        siblings = {
            item["rfilename"]: item for item in payload.get("siblings", [])
        }
        repo_files[kind] = set(siblings)
        if payload.get("private") is not False:
            errors.append(f"{repo_id}: repository is not public")
        if payload.get("sha") != repo["live_head"]:
            errors.append(
                f"{repo_id}: live head drifted: "
                f"{payload.get('sha')!r} != {repo['live_head']!r}"
            )
        for name, expected in _artifact_records(repo).items():
            actual = siblings.get(name)
            if actual is None:
                errors.append(f"{repo_id}: missing retained artifact {name}")
                continue
            if actual.get("size") != expected["size"]:
                errors.append(f"{repo_id}/{name}: size mismatch")
            if (actual.get("lfs") or {}).get("sha256") != expected["sha256"]:
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
            card = card_bytes.decode("utf-8")
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
