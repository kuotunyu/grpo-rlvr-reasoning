import json
import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]


def test_notebook_is_valid_json_without_stored_outputs():
    notebook = json.loads(
        (ROOT / "train_grpo_colab.ipynb").read_text(encoding="utf-8")
    )

    assert notebook["nbformat"] == 4
    outputs = [
        output
        for cell in notebook["cells"]
        for output in cell.get("outputs", [])
    ]
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
