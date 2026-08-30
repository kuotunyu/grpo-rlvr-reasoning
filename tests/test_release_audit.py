import json
from pathlib import Path

import release_audit
from hf_release import model_card_header, model_card_legal_section, model_notice
from release_audit import audit_public_release


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "docs" / "huggingface" / "remote-artifact-audit.json"
GITHUB_API_URL = "https://api.github.com/repos/kuotunyu/grpo-rlvr-reasoning"


def load_record():
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def make_remote_fixture():
    record = load_record()
    responses_json = {
        GITHUB_API_URL: {
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
        metadata_records = repo.get("artifacts", {}) | repo.get("adapter", {})
        for name, metadata in metadata_records.items():
            if not isinstance(metadata, dict) or "sha256" not in metadata:
                continue
            siblings.append(
                {
                    "rfilename": name,
                    "size": metadata["size"],
                    "lfs": {"sha256": metadata["sha256"]},
                }
            )
        siblings.extend(
            {"rfilename": name} for name in ("README.md", "LICENSE", "NOTICE")
        )
        responses_json[
            f"https://huggingface.co/api/models/{repo_id}?blobs=true"
        ] = {
            "private": False,
            "gated": False,
            "disabled": False,
            "sha": head,
            "siblings": siblings,
        }
        base = f"https://huggingface.co/{repo_id}/resolve/{head}"
        responses_bytes[f"{base}/README.md"] = (
            model_card_header(library_name=library)
            + "\nModel details\n"
            + model_card_legal_section()
        ).encode()
        responses_bytes[f"{base}/LICENSE"] = (
            ROOT / "LICENSES" / "QWEN-RESEARCH-LICENSE.txt"
        ).read_bytes()
        responses_bytes[f"{base}/NOTICE"] = model_notice().encode()
    return record, responses_json, responses_bytes


def test_audit_accepts_reviewed_public_release():
    record, json_map, bytes_map = make_remote_fixture()

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert errors == []


def test_audit_rejects_private_github_repo_and_wrong_default_branch():
    record, json_map, bytes_map = make_remote_fixture()
    json_map[GITHUB_API_URL]["private"] = True
    json_map[GITHUB_API_URL]["default_branch"] = "develop"

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert "GitHub: repository is not public" in errors
    assert "GitHub: default branch is not main" in errors


def test_audit_rejects_hf_head_drift():
    record, json_map, bytes_map = make_remote_fixture()
    repo_id = record["repositories"]["merged"]["repo_id"]
    json_map[f"https://huggingface.co/api/models/{repo_id}?blobs=true"][
        "sha"
    ] = "changed"

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert any(
        repo_id in error and "live head drifted" in error for error in errors
    )


def test_audit_rejects_private_hf_repo():
    record, json_map, bytes_map = make_remote_fixture()
    repo_id = record["repositories"]["lora"]["repo_id"]
    json_map[f"https://huggingface.co/api/models/{repo_id}?blobs=true"][
        "private"
    ] = True

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert f"{repo_id}: repository is not public" in errors


def test_audit_rejects_gated_hf_repo():
    record, json_map, bytes_map = make_remote_fixture()
    repo_id = record["repositories"]["lora"]["repo_id"]
    json_map[f"https://huggingface.co/api/models/{repo_id}?blobs=true"][
        "gated"
    ] = "manual"

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert f"{repo_id}: repository requires gated access" in errors


def test_audit_rejects_disabled_hf_repo():
    record, json_map, bytes_map = make_remote_fixture()
    repo_id = record["repositories"]["merged"]["repo_id"]
    json_map[f"https://huggingface.co/api/models/{repo_id}?blobs=true"][
        "disabled"
    ] = True

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert f"{repo_id}: repository is disabled" in errors


def test_audit_reports_missing_repository_record_without_traceback():
    record, json_map, bytes_map = make_remote_fixture()
    del record["repositories"]["lora"]

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert errors == ["audit record: missing repositories.lora object"]


def test_audit_reports_missing_repository_identifiers_without_traceback():
    record, json_map, bytes_map = make_remote_fixture()
    del record["repositories"]["merged"]["repo_id"]
    record["repositories"]["lora"]["live_head"] = None

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert errors == [
        "audit record: repositories.merged.repo_id must be a non-empty string",
        "audit record: repositories.lora.live_head must be a non-empty string",
    ]


def test_audit_reports_non_object_artifact_collections_without_traceback():
    record, json_map, bytes_map = make_remote_fixture()
    record["repositories"]["merged"]["artifacts"] = None
    record["repositories"]["lora"]["adapter"] = []

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert errors == [
        "audit record: repositories.merged.artifacts must be an object",
        "audit record: repositories.lora.adapter must be an object",
    ]


def test_audit_requires_all_reviewed_artifact_records():
    record, json_map, bytes_map = make_remote_fixture()
    del record["repositories"]["merged"]["artifacts"][
        "model-00002-of-00002.safetensors"
    ]
    del record["repositories"]["lora"]["adapter"][
        "adapter_model.safetensors"
    ]

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert errors == [
        "audit record: repositories.merged.artifacts."
        "model-00002-of-00002.safetensors is required",
        "audit record: repositories.lora.adapter."
        "adapter_model.safetensors is required",
    ]


def test_audit_rejects_malformed_reviewed_artifact_metadata():
    record, json_map, bytes_map = make_remote_fixture()
    merged = record["repositories"]["merged"]["artifacts"]
    adapter = record["repositories"]["lora"]["adapter"]
    merged["model-00001-of-00002.safetensors"]["size"] = True
    merged["model-00002-of-00002.safetensors"]["sha256"] = "z" * 64
    adapter["adapter_model.safetensors"]["size"] = 0
    adapter["adapter_model.safetensors"]["sha256"] = "abcd"

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert errors == [
        "audit record: repositories.merged.artifacts."
        "model-00001-of-00002.safetensors.size must be a positive integer",
        "audit record: repositories.merged.artifacts."
        "model-00002-of-00002.safetensors.sha256 must be 64 hexadecimal characters",
        "audit record: repositories.lora.adapter."
        "adapter_model.safetensors.size must be a positive integer",
        "audit record: repositories.lora.adapter."
        "adapter_model.safetensors.sha256 must be 64 hexadecimal characters",
    ]


def test_audit_reports_null_hf_siblings_without_traceback():
    record, json_map, bytes_map = make_remote_fixture()
    repo_id = record["repositories"]["merged"]["repo_id"]
    json_map[f"https://huggingface.co/api/models/{repo_id}?blobs=true"][
        "siblings"
    ] = None

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert f"{repo_id}: siblings must be a list" in errors


def test_audit_reports_sibling_without_filename_without_traceback():
    record, json_map, bytes_map = make_remote_fixture()
    repo_id = record["repositories"]["merged"]["repo_id"]
    json_map[f"https://huggingface.co/api/models/{repo_id}?blobs=true"][
        "siblings"
    ][0] = {}

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert f"{repo_id}: sibling 0 has invalid rfilename" in errors


def test_audit_reports_non_object_sibling_without_traceback():
    record, json_map, bytes_map = make_remote_fixture()
    repo_id = record["repositories"]["lora"]["repo_id"]
    json_map[f"https://huggingface.co/api/models/{repo_id}?blobs=true"][
        "siblings"
    ][0] = "adapter_config.json"

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert f"{repo_id}: sibling 0 must be an object" in errors


def test_audit_rejects_stale_full_model_file_in_lora():
    record, json_map, bytes_map = make_remote_fixture()
    repo_id = record["repositories"]["lora"]["repo_id"]
    json_map[f"https://huggingface.co/api/models/{repo_id}?blobs=true"][
        "siblings"
    ].append({"rfilename": "model-00001-of-00002.safetensors"})

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert any("LoRA repo contains full-model artifact" in error for error in errors)


def test_audit_rejects_missing_retained_artifact():
    record, json_map, bytes_map = make_remote_fixture()
    repo_id = record["repositories"]["lora"]["repo_id"]
    siblings = json_map[
        f"https://huggingface.co/api/models/{repo_id}?blobs=true"
    ]["siblings"]
    siblings[:] = [
        item
        for item in siblings
        if item["rfilename"] != "adapter_model.safetensors"
    ]

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert f"{repo_id}: missing retained artifact adapter_model.safetensors" in errors


def test_audit_rejects_changed_artifact_hash_and_size():
    record, json_map, bytes_map = make_remote_fixture()
    repo_id = record["repositories"]["merged"]["repo_id"]
    artifact = next(
        item
        for item in json_map[
            f"https://huggingface.co/api/models/{repo_id}?blobs=true"
        ]["siblings"]
        if item["rfilename"] == "model-00001-of-00002.safetensors"
    )
    artifact["size"] = 1
    artifact["lfs"]["sha256"] = "0" * 64

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert f"{repo_id}/{artifact['rfilename']}: size mismatch" in errors
    assert f"{repo_id}/{artifact['rfilename']}: SHA-256 mismatch" in errors


def test_audit_reports_non_object_lfs_metadata_without_traceback():
    record, json_map, bytes_map = make_remote_fixture()
    repo_id = record["repositories"]["merged"]["repo_id"]
    artifact = next(
        item
        for item in json_map[
            f"https://huggingface.co/api/models/{repo_id}?blobs=true"
        ]["siblings"]
        if item["rfilename"] == "model-00001-of-00002.safetensors"
    )
    artifact["lfs"] = "not-an-object"

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert (
        f"{repo_id}/{artifact['rfilename']}: lfs metadata must be an object"
        in errors
    )


def test_audit_rejects_changed_card_license_metadata_and_legal_section():
    record, json_map, bytes_map = make_remote_fixture()
    repo = record["repositories"]["lora"]
    card_url = (
        f"https://huggingface.co/{repo['repo_id']}/resolve/"
        f"{repo['live_head']}/README.md"
    )
    bytes_map[card_url] = b"---\nlicense: apache-2.0\n---\n"

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert f"{repo['repo_id']}/README.md: generated license header mismatch" in errors
    assert f"{repo['repo_id']}/README.md: generated legal section missing" in errors


def test_audit_reports_invalid_utf8_card_without_traceback():
    record, json_map, bytes_map = make_remote_fixture()
    repo = record["repositories"]["lora"]
    card_url = (
        f"https://huggingface.co/{repo['repo_id']}/resolve/"
        f"{repo['live_head']}/README.md"
    )
    bytes_map[card_url] = b"\xff"

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert f"{repo['repo_id']}/README.md: invalid UTF-8" in errors


def test_audit_rejects_changed_qwen_license_bytes():
    record, json_map, bytes_map = make_remote_fixture()
    repo = record["repositories"]["merged"]
    license_url = (
        f"https://huggingface.co/{repo['repo_id']}/resolve/"
        f"{repo['live_head']}/LICENSE"
    )
    bytes_map[license_url] = b"changed"

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert f"{repo['repo_id']}/LICENSE: size mismatch" in errors
    assert f"{repo['repo_id']}/LICENSE: SHA-256 mismatch" in errors


def test_audit_rejects_changed_qwen_notice():
    record, json_map, bytes_map = make_remote_fixture()
    repo = record["repositories"]["merged"]
    notice_url = (
        f"https://huggingface.co/{repo['repo_id']}/resolve/"
        f"{repo['live_head']}/NOTICE"
    )
    bytes_map[notice_url] = b"changed"

    errors = audit_public_release(
        record, json_map.__getitem__, bytes_map.__getitem__
    )

    assert f"{repo['repo_id']}/NOTICE: generated notice mismatch" in errors


def test_audit_reports_network_failure_without_traceback():
    record, _, bytes_map = make_remote_fixture()

    def fail(_url):
        raise OSError("offline")

    errors = audit_public_release(record, fail, bytes_map.__getitem__)

    assert errors
    assert all("Traceback" not in error for error in errors)
    assert any("unable to fetch" in error and "offline" in error for error in errors)


def test_audit_reports_small_file_fetch_failure_and_continues():
    record, json_map, _ = make_remote_fixture()

    def fail(_url):
        raise OSError("file host unavailable")

    errors = audit_public_release(record, json_map.__getitem__, fail)

    assert len([error for error in errors if "unable to fetch" in error]) == 6
    assert any("README.md" in error and "file host unavailable" in error for error in errors)
    assert any("LICENSE" in error and "file host unavailable" in error for error in errors)
    assert any("NOTICE" in error and "file host unavailable" in error for error in errors)


def test_main_prints_verified_heads_and_artifacts(monkeypatch, capsys):
    record, json_map, bytes_map = make_remote_fixture()
    monkeypatch.setattr(
        release_audit,
        "http_get_json",
        lambda url, timeout=15.0: json_map[url],
        raising=False,
    )
    monkeypatch.setattr(
        release_audit,
        "http_get_bytes",
        lambda url, timeout=15.0: bytes_map[url],
        raising=False,
    )

    return_code = release_audit.main(["--audit-record", str(AUDIT_PATH)])

    captured = capsys.readouterr()
    assert return_code == 0
    for kind in ("merged", "lora"):
        assert record["repositories"][kind]["live_head"] in captured.out
    assert "adapter_model.safetensors" in captured.out
    assert captured.err == ""


def test_main_reports_invalid_audit_record_without_traceback(tmp_path, capsys):
    invalid = tmp_path / "audit.json"
    invalid.write_text("not json", encoding="utf-8")

    return_code = release_audit.main(["--audit-record", str(invalid)])

    captured = capsys.readouterr()
    assert return_code == 1
    assert "ERROR: unable to read audit record" in captured.err
    assert "Traceback" not in captured.err


def test_main_returns_nonzero_and_prints_audit_errors(monkeypatch, capsys):
    _, json_map, bytes_map = make_remote_fixture()
    json_map[GITHUB_API_URL]["private"] = True
    monkeypatch.setattr(
        release_audit,
        "http_get_json",
        lambda url, timeout=15.0: json_map[url],
    )
    monkeypatch.setattr(
        release_audit,
        "http_get_bytes",
        lambda url, timeout=15.0: bytes_map[url],
    )

    return_code = release_audit.main(["--audit-record", str(AUDIT_PATH)])

    captured = capsys.readouterr()
    assert return_code == 1
    assert "ERROR: GitHub: repository is not public" in captured.err
    assert "verified " not in captured.out


def test_http_get_bytes_sets_headers_and_timeout(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b"payload"

    def fake_urlopen(request, timeout):
        captured["user_agent"] = request.get_header("User-agent")
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(release_audit.urllib.request, "urlopen", fake_urlopen)

    data = release_audit.http_get_bytes(GITHUB_API_URL, timeout=2.5)

    assert data == b"payload"
    assert captured == {
        "user_agent": "grpo-rlvr-release-audit/1.0",
        "authorization": "Bearer test-token",
        "timeout": 2.5,
    }


def test_http_get_json_decodes_object(monkeypatch):
    monkeypatch.setattr(
        release_audit,
        "_request",
        lambda url, timeout: b'{"private": false, "sha": "abc"}',
    )

    payload = release_audit.http_get_json("https://example.test/api", timeout=3.0)

    assert payload == {"private": False, "sha": "abc"}


def test_http_get_json_rejects_non_object(monkeypatch):
    monkeypatch.setattr(
        release_audit, "_request", lambda url, timeout: b'["not", "an", "object"]'
    )

    try:
        release_audit.http_get_json("https://example.test/api")
    except ValueError as exc:
        assert str(exc) == "expected a JSON object"
    else:
        raise AssertionError("non-object JSON was accepted")


def test_http_error_is_reported_concisely(monkeypatch):
    def fail(request, timeout):
        raise release_audit.urllib.error.HTTPError(
            request.full_url, 503, "Service Unavailable", None, None
        )

    monkeypatch.setattr(release_audit.urllib.request, "urlopen", fail)

    try:
        release_audit.http_get_bytes("https://example.test/file")
    except OSError as exc:
        assert str(exc) == "HTTP 503"
    else:
        raise AssertionError("HTTP error was not translated")
