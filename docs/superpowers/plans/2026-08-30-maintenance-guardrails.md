# Maintenance Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Protect the public repository from accidental main-branch changes, enable low-noise security maintenance, and provide one Traditional Chinese operating guide.

**Architecture:** Versioned repository artifacts define and test the human-facing workflow first. Those artifacts are merged through a normal pull request while main is still unprotected; security settings and branch protection are applied only after the exact merged commit is green. Every remote mutation is preceded by an API snapshot and followed by API read-back, with no destructive test push.

**Tech Stack:** Python 3.10–3.12, pytest, YAML, GitHub Actions, GitHub REST API, GitHub CLI, PowerShell.

## Global Constraints

- Work only in D:\AI-Portfolio\CC_github部隊\RL_Github\1_GRPORLVR_推理訓練 and kuotunyu/grpo-rlvr-reasoning.
- Do not change either Hugging Face repository or any out-of-scope local repository.
- Do not change, move, or delete the existing v1.0.0 tag or release.
- Do not run new model training or GPU evaluation.
- Keep release_audit.py and all repository-health tests dependency-free.
- Require pytest (3.10), pytest (3.11), and pytest (3.12), with strict up-to-date status checks.
- Require pull requests but zero approving reviews; do not add CODEOWNERS, signed commits, merge queue, or auto-merge.
- Apply branch protection last and never probe it with a direct push to main.
- Keep public release audit path-filtered and do not make it a universal required check.
- Use apply_patch for every repository file edit.

---

### Task 1: Add the versioned guardrail contract

**Files:**
- Create: .github/dependabot.yml
- Create: docs/MAINTENANCE.md
- Modify: README.md
- Modify: tests/test_repository_health.py

**Interfaces:**
- Consumes: Existing ROOT constant and rendered-link validation in tests/test_repository_health.py.
- Produces: A fenced-code-aware link check, a weekly grouped GitHub Actions update policy, and a single maintainer guide.

- [ ] **Step 1: Create an isolated implementation worktree**

Use the using-git-worktrees skill. The implementation branch must start at the
commit containing this plan, use the name maintenance/guardrails, and use the
exact worktree path
D:\AI-Portfolio\CC_github部隊\RL_Github\1_GRPORLVR_推理訓練\.worktrees\maintenance-guardrails.

Run:

~~~powershell
git status --short
git rev-parse HEAD
git branch --show-current
~~~

Expected: clean status on the planning branch, with the design and plan commits present.

- [ ] **Step 2: Confirm the fenced-code link-check failure (RED)**

Run:

~~~powershell
python -m pytest tests/test_repository_health.py::test_local_markdown_links_exist -vv
~~~

Expected: FAIL with two false missing-link reports from this plan's fenced code
examples. This is the required RED evidence; do not add another source-text
test.

- [ ] **Step 3: Make the link checker inspect rendered Markdown only (GREEN)**

Add this helper below ROOT in tests/test_repository_health.py:

~~~python
MARKDOWN_FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")


def _rendered_markdown_text(text):
    rendered_lines = []
    fence_character = None
    fence_length = 0
    for line in text.splitlines():
        match = MARKDOWN_FENCE_PATTERN.match(line)
        if match:
            marker = match.group(1)
            if fence_character is None:
                fence_character = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_length:
                fence_character = None
                fence_length = 0
            continue
        if fence_character is None:
            rendered_lines.append(line)
    return "\n".join(rendered_lines)
~~~

In test_local_markdown_links_exist, replace the raw-file pattern input with:

~~~python
        rendered_text = _rendered_markdown_text(
            markdown.read_text(encoding="utf-8")
        )
        for raw_target in pattern.findall(rendered_text):
~~~

Run:

~~~powershell
python -m pytest tests/test_repository_health.py::test_local_markdown_links_exist -vv
~~~

Expected: PASS. The existing test remains capable of rejecting a missing link
that is actually rendered, while links inside backtick or tilde fences are
ignored.

- [ ] **Step 4: Create the Dependabot configuration**

Create .github/dependabot.yml with exactly:

~~~yaml
version: 2

updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
      timezone: "Asia/Taipei"
    groups:
      github-actions:
        patterns:
          - "*"
    open-pull-requests-limit: 3
    commit-message:
      prefix: "ci"
~~~

- [ ] **Step 5: Create the maintainer guide**

Create docs/MAINTENANCE.md with this content:

~~~~markdown
# 維護與發布防呆指南

這是本 repo 唯一的操作入口。若不確定下一步，先停止操作，把想做的變更和目前畫面交給 Codex；不需要自行猜 Git、GitHub 或 Hugging Face 指令。

## 1. 預設做法

- 描述想修改的內容、成功條件，以及是否涉及 GitHub release 或 HF 模型。
- 讓 Codex 建立 branch、執行測試、開 PR 並核對遠端狀態。
- 不要 force-push、不要重寫公開歷史、不要刪除 main。
- 不要移動或重建既有 release tag；已發布版本有問題時，建立新版本。
- 不要直接寫入、刪除或重寫 HF default branch。

## 2. 一般 GitHub 修改

必要流程只有：

1. 從最新 main 建立新 branch。
2. 修改並執行本機測試。
3. push branch 並建立 PR。
4. 等待 pytest (3.10)、pytest (3.11)、pytest (3.12) 全綠。
5. 解決所有 review 對話後再 merge。

不需要找其他人批准；CI 全綠且對話已解決即可自行 merge。不要繞過失敗的檢查，也不要直接 push 到 main。

## 3. 發布 GitHub 版本

發布前執行：

~~~bash
python -m pytest -q
python eval/verify_results.py
python release_audit.py
~~~

接著讓變更經 PR 合併，確認 main 的 CI 全綠，再建立新的版本號與 release notes。既有 tag 永遠保持指向原 commit；修正內容使用下一個版本號。

## 4. 修改 Hugging Face

HF 變更只走 candidate PR：

1. 建立 candidate revision，不直接寫 default branch。
2. 稽核 candidate 的檔案種類、授權文字、大小與 SHA-256。
3. 提交 HF PR 並等待人工核准。
4. merge 後執行 python release_audit.py。

不要直接寫入、刪除或重寫 HF default branch。不要把 GitHub 的 Apache-2.0 誤當成模型權重授權。

## 5. 檢查失敗時

- 停止 merge，不要 bypass。
- 保留完整錯誤輸出、失敗 run URL 和 commit SHA。
- 把證據交給 Codex 診斷。
- 修正必須透過同一個 PR 或新的修復 PR，再讓全部檢查重跑。

## 6. 復原方式

公開歷史只用新的 revert PR 復原。不要 force-push，也不要刪除或重建 release tag。若 HF 發布有問題，先停止下載宣傳與後續 merge，再以新的 candidate PR 修正；不要重寫遠端歷史。

## 哪些事情不必做

- 一般文件或程式修改不需要碰 HF。
- 沒有新模型 artifact 時，不需要改 remote artifact audit。
- 沒有新的使用者可見版本時，不需要建立 release。
- 既有 2026-07 評測不需要為每次文件更新重新跑 GPU。
~~~~

When applying this step, use a four-tilde outer patch fence or otherwise preserve the nested bash fence exactly.

- [ ] **Step 6: Add the README entrypoint**

Insert this section immediately before the existing License 與第三方內容 section in README.md:

~~~markdown
## 維護與發布

為避免誤推 main、錯誤移動 release tag 或直接改寫 Hugging Face，所有後續操作統一依
[維護與發布防呆指南](docs/MAINTENANCE.md)進行。不確定時先停止操作並交給 Codex
檢查，不要自行 bypass CI 或重寫公開歷史。

~~~

- [ ] **Step 7: Run the focused tests and verify they pass**

Run:

~~~powershell
python -m pytest tests/test_repository_health.py -q
~~~

Expected: all repository-health tests pass.

- [ ] **Step 8: Parse the YAML without changing project dependencies**

Run:

~~~powershell
python -c "import yaml, pathlib; data=yaml.safe_load(pathlib.Path('.github/dependabot.yml').read_text(encoding='utf-8')); expected={'version':2,'updates':[{'package-ecosystem':'github-actions','directory':'/','schedule':{'interval':'weekly','day':'monday','time':'09:00','timezone':'Asia/Taipei'},'groups':{'github-actions':{'patterns':['*']}},'open-pull-requests-limit':3,'commit-message':{'prefix':'ci'}}]}; assert data == expected, data; print('dependabot YAML parsed and matched')"
~~~

Expected: dependabot YAML parsed and matched. This is a semantic configuration
check, not a source-text grep; do not add PyYAML to the repository or CI.

- [ ] **Step 9: Commit the versioned guardrails**

Run:

~~~powershell
git add .github/dependabot.yml docs/MAINTENANCE.md README.md tests/test_repository_health.py
git commit -m "docs: add maintenance guardrails"
~~~

Expected: one focused commit containing only the four listed files.

### Task 2: Verify the implementation branch

**Files:**
- Verify only; no file changes expected.

**Interfaces:**
- Consumes: The committed guardrail artifacts from Task 1.
- Produces: Local evidence that the implementation is safe to publish.

- [ ] **Step 1: Run the Python 3.10 suite and offline gates**

Run:

~~~powershell
python --version
python -m pytest -q
python eval/verify_results.py
python -m compileall -q rewards.py hf_release.py release_audit.py eval tests
git diff --check
git status --short
~~~

Expected: Python 3.10, all tests pass, result artifacts match, compilation succeeds, no diff errors, and a clean worktree.

- [ ] **Step 2: Run the Python 3.11 and 3.12 suites**

Run:

~~~powershell
uv run --no-project --python 3.11 --with pytest python -m pytest -q
uv run --no-project --python 3.12 --with pytest python -m pytest -q
~~~

Expected: the same test count passes under both interpreters.

- [ ] **Step 3: Run the live read-only release audit**

Run:

~~~powershell
python release_audit.py
~~~

Expected: both pinned HF heads and all three retained artifact hashes are verified without downloading model weights.

- [ ] **Step 4: Confirm the existing release is unchanged**

Run:

~~~powershell
git rev-parse "v1.0.0^{commit}"
gh release view v1.0.0 --repo kuotunyu/grpo-rlvr-reasoning --json tagName,targetCommitish,isDraft,isPrerelease,url
~~~

Expected: v1.0.0 still resolves to 61eb57ccd0029f340d359d28700ee2bd50f47849 and remains a published non-prerelease.

### Task 3: Publish and merge the maintenance pull request

**Files:**
- Publish only; no file changes expected.

**Interfaces:**
- Consumes: Clean, verified maintenance/guardrails branch.
- Produces: One reviewed GitHub PR and an exact green merge commit on main.

- [ ] **Step 1: Push the implementation branch**

Run:

~~~powershell
git push -u origin maintenance/guardrails
~~~

Expected: the remote branch is created; main is unchanged.

- [ ] **Step 2: Create the pull request**

Run:

~~~powershell
gh pr create --repo kuotunyu/grpo-rlvr-reasoning --base main --head maintenance/guardrails --title "chore: add maintenance guardrails" --body "Adds a single Traditional Chinese maintainer guide, grouped weekly GitHub Actions updates, and dependency-free contract tests. No model artifacts, release tags, or Hugging Face repositories are changed."
~~~

Expected: one open PR URL.

- [ ] **Step 3: Wait for every PR check**

Run:

~~~powershell
$guardrailPr = gh pr view maintenance/guardrails --repo kuotunyu/grpo-rlvr-reasoning --json number --jq .number
gh pr checks $guardrailPr --repo kuotunyu/grpo-rlvr-reasoning --watch --fail-fast
~~~

Expected: pytest (3.10), pytest (3.11), and pytest (3.12) succeed. The public release audit may be absent because its paths are not changed.

- [ ] **Step 4: Review the PR diff before merge**

Run:

~~~powershell
$guardrailPr = gh pr view maintenance/guardrails --repo kuotunyu/grpo-rlvr-reasoning --json number --jq .number
gh pr diff $guardrailPr --repo kuotunyu/grpo-rlvr-reasoning --name-only
gh pr view $guardrailPr --repo kuotunyu/grpo-rlvr-reasoning --json files,reviewDecision,mergeStateStatus,statusCheckRollup,url
~~~

Expected: only the spec, plan, Dependabot configuration, maintainer guide, README, and repository-health test are present; mergeStateStatus is mergeable after checks finish.

- [ ] **Step 5: Merge the PR while preserving the reviewed commits**

Run:

~~~powershell
$guardrailPr = gh pr view maintenance/guardrails --repo kuotunyu/grpo-rlvr-reasoning --json number --jq .number
gh pr merge $guardrailPr --repo kuotunyu/grpo-rlvr-reasoning --merge --subject "chore: add maintenance guardrails"
~~~

Expected: the PR is merged with the reviewed design, plan, and implementation
commits preserved; no tag or release is created. Preserving ancestry allows the
local planning and implementation branches to be deleted with the safe -d
check after main is fast-forwarded.

- [ ] **Step 6: Capture the exact merge commit and wait for main CI**

Run:

~~~powershell
$guardrailPr = gh pr view maintenance/guardrails --repo kuotunyu/grpo-rlvr-reasoning --json number --jq .number
$guardrailMergeSha = gh pr view $guardrailPr --repo kuotunyu/grpo-rlvr-reasoning --json mergeCommit --jq .mergeCommit.oid
gh run list --repo kuotunyu/grpo-rlvr-reasoning --commit $guardrailMergeSha --limit 10 --json databaseId,name,status,conclusion,headSha,url
~~~

Wait for the tests run with that exact head SHA:

~~~powershell
$guardrailPr = gh pr view maintenance/guardrails --repo kuotunyu/grpo-rlvr-reasoning --json number --jq .number
$guardrailMergeSha = gh pr view $guardrailPr --repo kuotunyu/grpo-rlvr-reasoning --json mergeCommit --jq .mergeCommit.oid
$guardrailTestsRun = gh run list --repo kuotunyu/grpo-rlvr-reasoning --commit $guardrailMergeSha --workflow tests --limit 1 --json databaseId --jq '.[0].databaseId'
gh run watch $guardrailTestsRun --repo kuotunyu/grpo-rlvr-reasoning --exit-status
~~~

Expected: all three matrix jobs succeed on the exact merged main commit.

- [ ] **Step 7: Verify the merged Dependabot configuration from GitHub**

Run:

~~~powershell
$guardrailPr = gh pr view maintenance/guardrails --repo kuotunyu/grpo-rlvr-reasoning --json number --jq .number
$guardrailMergeSha = gh pr view $guardrailPr --repo kuotunyu/grpo-rlvr-reasoning --json mergeCommit --jq .mergeCommit.oid
$guardrailRemoteConfig = gh api "repos/kuotunyu/grpo-rlvr-reasoning/contents/.github/dependabot.yml?ref=$guardrailMergeSha" | ConvertFrom-Json
if ($guardrailRemoteConfig.path -ne ".github/dependabot.yml") { throw "Dependabot config missing from merged commit" }
$guardrailRemoteYaml = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(($guardrailRemoteConfig.content -replace '\s', '')))
$guardrailRemoteYaml | python -c "import sys,yaml; data=yaml.safe_load(sys.stdin.read()); expected={'version':2,'updates':[{'package-ecosystem':'github-actions','directory':'/','schedule':{'interval':'weekly','day':'monday','time':'09:00','timezone':'Asia/Taipei'},'groups':{'github-actions':{'patterns':['*']}},'open-pull-requests-limit':3,'commit-message':{'prefix':'ci'}}]}; assert data == expected, data; print('remote dependabot YAML parsed and matched')"
~~~

Expected: the exact merged GitHub blob parses and matches the approved
configuration. GitHub will consume this default-branch file on its next
Dependabot schedule.

### Task 4: Enable repository security maintenance

**Files:**
- Remote GitHub repository settings only.

**Interfaces:**
- Consumes: Green main merge commit and current repository security state.
- Produces: Enabled vulnerability alerts, enabled Dependabot security updates, automatic merged-branch cleanup, and preserved secret protections.

- [ ] **Step 1: Snapshot the current remote settings**

Run:

~~~powershell
gh api repos/kuotunyu/grpo-rlvr-reasoning --jq '{visibility,default_branch,allow_auto_merge,delete_branch_on_merge,security_and_analysis}'
gh api -i repos/kuotunyu/grpo-rlvr-reasoning/vulnerability-alerts 2>&1
gh api -i repos/kuotunyu/grpo-rlvr-reasoning/automated-security-fixes 2>&1
~~~

Expected baseline from design: public main; auto-merge false; delete_branch_on_merge false; secret scanning and push protection enabled; vulnerability alerts and Dependabot security updates disabled. If the state differs, stop and reconcile it before mutation.

- [ ] **Step 2: Enable vulnerability alerts**

Run:

~~~powershell
gh api --method PUT repos/kuotunyu/grpo-rlvr-reasoning/vulnerability-alerts
~~~

Expected: HTTP 204 / successful empty response.

- [ ] **Step 3: Enable Dependabot security updates**

Run:

~~~powershell
gh api --method PUT repos/kuotunyu/grpo-rlvr-reasoning/automated-security-fixes
~~~

Expected: HTTP 204 / successful empty response.

- [ ] **Step 4: Enable merged-branch cleanup while keeping auto-merge off**

Run:

~~~powershell
gh api --method PATCH repos/kuotunyu/grpo-rlvr-reasoning -F delete_branch_on_merge=true -F allow_auto_merge=false
~~~

Expected: delete_branch_on_merge true and allow_auto_merge false.

- [ ] **Step 5: Read back and validate the security state**

Run:

~~~powershell
gh api -i repos/kuotunyu/grpo-rlvr-reasoning/vulnerability-alerts
gh api repos/kuotunyu/grpo-rlvr-reasoning --jq '{allow_auto_merge,delete_branch_on_merge,security_and_analysis}'
~~~

Expected: vulnerability-alert endpoint returns 204; Dependabot security updates, secret scanning, and push protection are enabled; merged-branch deletion is enabled; auto-merge is false.

If any validation fails, restore only settings changed from the captured baseline:

~~~powershell
gh api --method DELETE repos/kuotunyu/grpo-rlvr-reasoning/vulnerability-alerts
gh api --method DELETE repos/kuotunyu/grpo-rlvr-reasoning/automated-security-fixes
gh api --method PATCH repos/kuotunyu/grpo-rlvr-reasoning -F delete_branch_on_merge=false -F allow_auto_merge=false
~~~

### Task 5: Apply and verify main branch protection

**Files:**
- Remote GitHub main branch settings only.

**Interfaces:**
- Consumes: Exact green main merge SHA and GitHub Actions check-run metadata.
- Produces: PR-only main with three strict CI checks, administrator enforcement, conversation resolution, and destructive operations disabled.

- [ ] **Step 1: Confirm main still has no protection**

Run:

~~~powershell
gh api repos/kuotunyu/grpo-rlvr-reasoning/branches/main/protection 2>&1
~~~

Expected: HTTP 404 Branch not protected. If protection now exists, stop and compare it with the spec instead of overwriting it.

- [ ] **Step 2: Resolve the GitHub Actions app ID from the green main checks**

Run:

~~~powershell
$guardrailMergeSha = gh api repos/kuotunyu/grpo-rlvr-reasoning/commits/main --jq .sha
$guardrailCheckNames = @("pytest (3.10)", "pytest (3.11)", "pytest (3.12)")
$guardrailCheckRuns = gh api "repos/kuotunyu/grpo-rlvr-reasoning/commits/$guardrailMergeSha/check-runs?per_page=100" | ConvertFrom-Json
$guardrailRequiredRuns = @($guardrailCheckRuns.check_runs | Where-Object { $guardrailCheckNames -ccontains $_.name })
foreach ($guardrailCheckName in $guardrailCheckNames) {
    $guardrailNamedRuns = @($guardrailRequiredRuns | Where-Object { $_.name -ceq $guardrailCheckName })
    if ($guardrailNamedRuns.Count -ne 1) { throw "Expected exactly one $guardrailCheckName check run; found $($guardrailNamedRuns.Count)" }
    $guardrailNamedRun = $guardrailNamedRuns[0]
    if ($guardrailNamedRun.status -cne "completed" -or $guardrailNamedRun.conclusion -cne "success") { throw "$guardrailCheckName is not completed successfully" }
    if ($guardrailNamedRun.app.slug -cne "github-actions") { throw "$guardrailCheckName was not produced by GitHub Actions" }
}
$guardrailActionAppIds = @($guardrailRequiredRuns | ForEach-Object { [long]$_.app.id } | Sort-Object -Unique)
if ($guardrailActionAppIds.Count -ne 1 -or $guardrailActionAppIds[0] -le 0) { throw "Expected one positive GitHub Actions app id for all required checks" }
$guardrailActionsAppId = [long]$guardrailActionAppIds[0]
$guardrailActionsAppId
~~~

Expected: one positive GitHub Actions app ID shared by all three checks.

- [ ] **Step 3: Build and apply the exact protection payload**

Use `checks` instead of the legacy `contexts` field when binding required
checks to a GitHub App. Do not submit both fields together; GitHub rejects that
mixed representation.

Run:

~~~powershell
$guardrailMergeSha = gh api repos/kuotunyu/grpo-rlvr-reasoning/commits/main --jq .sha
$guardrailCheckNames = @("pytest (3.10)", "pytest (3.11)", "pytest (3.12)")
$guardrailCheckRuns = gh api "repos/kuotunyu/grpo-rlvr-reasoning/commits/$guardrailMergeSha/check-runs?per_page=100" | ConvertFrom-Json
$guardrailRequiredRuns = @($guardrailCheckRuns.check_runs | Where-Object { $guardrailCheckNames -ccontains $_.name })
foreach ($guardrailCheckName in $guardrailCheckNames) {
    $guardrailNamedRuns = @($guardrailRequiredRuns | Where-Object { $_.name -ceq $guardrailCheckName })
    if ($guardrailNamedRuns.Count -ne 1) { throw "Expected exactly one $guardrailCheckName check run; found $($guardrailNamedRuns.Count)" }
    $guardrailNamedRun = $guardrailNamedRuns[0]
    if ($guardrailNamedRun.status -cne "completed" -or $guardrailNamedRun.conclusion -cne "success") { throw "$guardrailCheckName is not completed successfully" }
    if ($guardrailNamedRun.app.slug -cne "github-actions") { throw "$guardrailCheckName was not produced by GitHub Actions" }
}
$guardrailActionAppIds = @($guardrailRequiredRuns | ForEach-Object { [long]$_.app.id } | Sort-Object -Unique)
if ($guardrailActionAppIds.Count -ne 1 -or $guardrailActionAppIds[0] -le 0) { throw "Expected one positive GitHub Actions app id for all required checks" }
$guardrailActionsAppId = [long]$guardrailActionAppIds[0]
$guardrailRequiredChecks = @(
    @{ context = "pytest (3.10)"; app_id = $guardrailActionsAppId },
    @{ context = "pytest (3.11)"; app_id = $guardrailActionsAppId },
    @{ context = "pytest (3.12)"; app_id = $guardrailActionsAppId }
)
$guardrailProtectionPayload = @{
    required_status_checks = @{
        strict = $true
        checks = $guardrailRequiredChecks
    }
    enforce_admins = $true
    required_pull_request_reviews = @{
        dismiss_stale_reviews = $false
        require_code_owner_reviews = $false
        required_approving_review_count = 0
        require_last_push_approval = $false
    }
    restrictions = $null
    required_linear_history = $false
    allow_force_pushes = $false
    allow_deletions = $false
    block_creations = $false
    required_conversation_resolution = $true
    lock_branch = $false
    allow_fork_syncing = $false
} | ConvertTo-Json -Depth 10 -Compress
$guardrailProtectionPayload | gh api --method PUT repos/kuotunyu/grpo-rlvr-reasoning/branches/main/protection --input -
~~~

Expected: HTTP 200 and a branch-protection object.

- [ ] **Step 4: Read back and assert every protection field**

Run:

~~~powershell
$guardrailMergeSha = gh api repos/kuotunyu/grpo-rlvr-reasoning/commits/main --jq .sha
$guardrailCheckNames = @("pytest (3.10)", "pytest (3.11)", "pytest (3.12)")
$guardrailCheckRuns = gh api "repos/kuotunyu/grpo-rlvr-reasoning/commits/$guardrailMergeSha/check-runs?per_page=100" | ConvertFrom-Json
$guardrailRequiredRuns = @($guardrailCheckRuns.check_runs | Where-Object { $guardrailCheckNames -ccontains $_.name })
foreach ($guardrailCheckName in $guardrailCheckNames) {
    $guardrailNamedRuns = @($guardrailRequiredRuns | Where-Object { $_.name -ceq $guardrailCheckName })
    if ($guardrailNamedRuns.Count -ne 1) { throw "Expected exactly one $guardrailCheckName check run; found $($guardrailNamedRuns.Count)" }
    $guardrailNamedRun = $guardrailNamedRuns[0]
    if ($guardrailNamedRun.status -cne "completed" -or $guardrailNamedRun.conclusion -cne "success") { throw "$guardrailCheckName is not completed successfully" }
    if ($guardrailNamedRun.app.slug -cne "github-actions") { throw "$guardrailCheckName was not produced by GitHub Actions" }
}
$guardrailActionAppIds = @($guardrailRequiredRuns | ForEach-Object { [long]$_.app.id } | Sort-Object -Unique)
if ($guardrailActionAppIds.Count -ne 1 -or $guardrailActionAppIds[0] -le 0) { throw "Expected one positive GitHub Actions app id for all required checks" }
$guardrailActionsAppId = [long]$guardrailActionAppIds[0]
$guardrailProtection = gh api repos/kuotunyu/grpo-rlvr-reasoning/branches/main/protection | ConvertFrom-Json
if ($null -eq $guardrailProtection.required_status_checks) { throw "Required status checks are missing" }
$guardrailActualChecks = @($guardrailProtection.required_status_checks.checks | ForEach-Object { "$($_.context)|$([long]$_.app_id)" } | Sort-Object)
$guardrailExpectedChecks = @($guardrailCheckNames | ForEach-Object { "$_|$guardrailActionsAppId" } | Sort-Object)
if ($guardrailActualChecks.Count -ne $guardrailExpectedChecks.Count -or (Compare-Object $guardrailExpectedChecks $guardrailActualChecks)) { throw "Required context and app-id pairs do not match" }
if ($guardrailProtection.required_status_checks.strict -ne $true) { throw "Strict checks are disabled" }
if ($guardrailProtection.enforce_admins.enabled -ne $true) { throw "Admin enforcement is disabled" }
if ($null -eq $guardrailProtection.required_pull_request_reviews) { throw "Pull-request review protection is missing" }
if ($guardrailProtection.required_pull_request_reviews.required_approving_review_count -ne 0) { throw "Review count is not zero" }
if ($guardrailProtection.required_pull_request_reviews.dismiss_stale_reviews -ne $false) { throw "Stale-review dismissal is enabled or missing" }
if ($guardrailProtection.required_pull_request_reviews.require_code_owner_reviews -ne $false) { throw "Code-owner reviews are enabled or missing" }
if ($guardrailProtection.required_pull_request_reviews.require_last_push_approval -ne $false) { throw "Last-push approval is enabled or missing" }
if ($null -ne $guardrailProtection.restrictions) { throw "Push restrictions are unexpectedly configured" }
if ($guardrailProtection.required_conversation_resolution.enabled -ne $true) { throw "Conversation resolution is disabled" }
if ($guardrailProtection.allow_force_pushes.enabled -ne $false) { throw "Force pushes are enabled or missing" }
if ($guardrailProtection.allow_deletions.enabled -ne $false) { throw "Branch deletion is enabled or missing" }
if ($guardrailProtection.block_creations.enabled -ne $false) { throw "Branch creation blocking is enabled or missing" }
if ($guardrailProtection.required_linear_history.enabled -ne $false) { throw "Linear history is unexpectedly required or missing" }
if ($guardrailProtection.lock_branch.enabled -ne $false) { throw "Main is unexpectedly locked or missing" }
if ($guardrailProtection.allow_fork_syncing.enabled -ne $false) { throw "Fork syncing is enabled or missing" }
"branch protection verified"
~~~

Expected: branch protection verified.

If validation fails and the baseline in Step 1 was unprotected, immediately restore that exact baseline:

~~~powershell
gh api --method DELETE repos/kuotunyu/grpo-rlvr-reasoning/branches/main/protection
~~~

Then report the mismatched fields instead of retrying with guessed values.

### Task 6: Final end-to-end verification and cleanup

**Files:**
- Verify only; remove only the exact temporary worktree and merged implementation branch.

**Interfaces:**
- Consumes: Green main commit and verified remote settings.
- Produces: Final evidence, a clean local checkout, and no stale maintenance branch.

- [ ] **Step 1: Verify the exact main and release identities**

Run:

~~~powershell
git fetch origin main --tags
git rev-parse origin/main
git rev-parse "v1.0.0^{commit}"
gh release view v1.0.0 --repo kuotunyu/grpo-rlvr-reasoning --json tagName,targetCommitish,isDraft,isPrerelease,url
~~~

Expected: origin/main is the maintenance merge SHA; v1.0.0 remains at 61eb57ccd0029f340d359d28700ee2bd50f47849 and remains published.

- [ ] **Step 2: Fast-forward the main checkout and re-run verification**

Run from any PowerShell session:

~~~powershell
$guardrailRepo = "D:\AI-Portfolio\CC_github部隊\RL_Github\1_GRPORLVR_推理訓練"
if (git -C $guardrailRepo status --porcelain) { throw "Main checkout is not clean" }
git -C $guardrailRepo switch main
git -C $guardrailRepo fetch origin main
git -C $guardrailRepo merge --ff-only origin/main
Set-Location -LiteralPath $guardrailRepo
python -m pytest -q
python eval/verify_results.py
python release_audit.py
git status --short
~~~

Expected: all tests pass, result artifacts match, live GitHub/HF release surfaces pass, and the checkout is clean.

- [ ] **Step 3: Perform one final remote settings audit**

Run:

~~~powershell
gh api repos/kuotunyu/grpo-rlvr-reasoning --jq '{visibility,default_branch,allow_auto_merge,delete_branch_on_merge,security_and_analysis}'
gh api -i repos/kuotunyu/grpo-rlvr-reasoning/vulnerability-alerts
gh api repos/kuotunyu/grpo-rlvr-reasoning/branches/main/protection --jq '{required_status_checks,enforce_admins,required_pull_request_reviews,required_conversation_resolution,allow_force_pushes,allow_deletions,required_linear_history,lock_branch}'
~~~

Expected: every acceptance criterion in the approved design is visible in the read-back.

- [ ] **Step 4: Remove the exact completed worktree and maintenance branches**

First confirm the PR is merged and run this from the primary checkout. The
script pins both fetch and push URLs, refreshes only the exact `origin/main`
ref, uses an OID lease for the exact remote deletion, and removes only an exact
stale remote-tracking ref. It then inventories tracked, untracked, and ignored
worktree content before removing explicitly enumerated disposable task data:

~~~powershell
$ErrorActionPreference = "Stop"
$guardrailRepo = "D:\AI-Portfolio\CC_github部隊\RL_Github\1_GRPORLVR_推理訓練"
$guardrailExpectedOrigin = "https://github.com/kuotunyu/grpo-rlvr-reasoning.git"
$guardrailRemoteBranchRef = "refs/heads/maintenance/guardrails"
$guardrailTrackingBranchRef = "refs/remotes/origin/maintenance/guardrails"
$guardrailOriginMainRef = "refs/remotes/origin/main"
$guardrailWorktreeBranchRef = "refs/heads/maintenance/guardrails"
$guardrailPlanningBranchRef = "refs/heads/docs/maintenance-guardrails-spec"

function Assert-GuardrailFullOid {
    param([string]$Oid, [string]$Label)
    if ($Oid -notmatch '\A[0-9a-f]{40}\z') { throw "$Label is not one full SHA-1 OID: $Oid" }
}

function Get-GuardrailWorktreeRecords {
    $guardrailWorktreeLines = @(git -C $guardrailRepo worktree list --porcelain)
    if ($LASTEXITCODE -ne 0) { throw "Unable to read registered worktrees" }
    $guardrailRecords = [Collections.Generic.List[object]]::new()
    $guardrailRecord = $null
    foreach ($guardrailLine in @($guardrailWorktreeLines) + @("")) {
        if ($guardrailLine.StartsWith("worktree ", [StringComparison]::Ordinal)) {
            if ($null -ne $guardrailRecord) { throw "Malformed worktree registry" }
            $guardrailRecord = [ordered]@{ Path = $guardrailLine.Substring(9); Head = $null; Branch = $null }
        } elseif ($guardrailLine -eq "") {
            if ($null -ne $guardrailRecord) {
                $guardrailRecords.Add([pscustomobject]$guardrailRecord)
                $guardrailRecord = $null
            }
        } elseif ($null -eq $guardrailRecord) {
            throw "Malformed worktree registry line: $guardrailLine"
        } elseif ($guardrailLine.StartsWith("HEAD ", [StringComparison]::Ordinal)) {
            if ($null -ne $guardrailRecord.Head) { throw "Duplicate worktree HEAD" }
            $guardrailRecord.Head = $guardrailLine.Substring(5)
        } elseif ($guardrailLine.StartsWith("branch ", [StringComparison]::Ordinal)) {
            if ($null -ne $guardrailRecord.Branch) { throw "Duplicate worktree branch" }
            $guardrailRecord.Branch = $guardrailLine.Substring(7)
        } else {
            throw "Unexpected worktree registry line: $guardrailLine"
        }
    }
    return $guardrailRecords.ToArray()
}

function Remove-GuardrailDisposableDirectory {
    param([string]$LiteralPath, [string]$WorktreePath)
    $guardrailFullPath = [IO.Path]::GetFullPath($LiteralPath)
    if (-not $guardrailFullPath.StartsWith($WorktreePath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "Disposable directory escaped worktree: $guardrailFullPath" }
    if (-not (Test-Path -LiteralPath $guardrailFullPath)) { return }
    $guardrailItem = Get-Item -LiteralPath $guardrailFullPath -Force
    if (-not $guardrailItem.PSIsContainer -or ($guardrailItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Disposable path is not an ordinary directory: $guardrailFullPath" }
    $guardrailAncestor = $guardrailItem
    while (-not $guardrailAncestor.FullName.Equals($WorktreePath, [StringComparison]::OrdinalIgnoreCase)) {
        if ($guardrailAncestor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point in disposable path: $($guardrailAncestor.FullName)" }
        $guardrailAncestor = $guardrailAncestor.Parent
        if ($null -eq $guardrailAncestor) { throw "Disposable path escaped worktree ancestry" }
    }
    $guardrailDescendants = @(Get-ChildItem -LiteralPath $guardrailFullPath -Force -Recurse)
    if (@($guardrailDescendants | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count -ne 0) { throw "Reparse point inside disposable directory: $guardrailFullPath" }
    Remove-Item -LiteralPath $guardrailFullPath -Recurse
    if (Test-Path -LiteralPath $guardrailFullPath) { throw "Disposable directory removal failed: $guardrailFullPath" }
}

function Assert-GuardrailMainExactAndClean {
    param([string]$ExpectedOid)
    $guardrailMainRefs = @(git -C $guardrailRepo symbolic-ref --quiet HEAD)
    if ($LASTEXITCODE -ne 0 -or $guardrailMainRefs.Count -ne 1 -or $guardrailMainRefs[0] -ne "refs/heads/main") { throw "Primary checkout is not attached to main" }
    $guardrailMainOids = @(git -C $guardrailRepo rev-parse --verify "HEAD^{commit}")
    if ($LASTEXITCODE -ne 0 -or $guardrailMainOids.Count -ne 1) { throw "Unable to resolve primary main HEAD" }
    Assert-GuardrailFullOid $guardrailMainOids[0] "primary main HEAD"
    if ($guardrailMainOids[0] -ne $ExpectedOid) { throw "Primary main is not exact origin/main" }
    $guardrailMainStatus = @(git -C $guardrailRepo status --porcelain=v1 --untracked-files=all)
    if ($LASTEXITCODE -ne 0) { throw "Unable to inspect primary main status" }
    if ($guardrailMainStatus.Count -ne 0) { throw "Primary main checkout is not clean" }
}

$guardrailFetchUrls = @(git -C $guardrailRepo remote get-url --all origin)
if ($LASTEXITCODE -ne 0) { throw "Unable to resolve origin fetch URL" }
if ($guardrailFetchUrls.Count -ne 1 -or $guardrailFetchUrls[0] -ne $guardrailExpectedOrigin) { throw "Unexpected origin fetch URLs: $($guardrailFetchUrls -join ', ')" }
$guardrailPushUrls = @(git -C $guardrailRepo remote get-url --push --all origin)
if ($LASTEXITCODE -ne 0) { throw "Unable to resolve origin push URL" }
if ($guardrailPushUrls.Count -ne 1 -or $guardrailPushUrls[0] -ne $guardrailExpectedOrigin) { throw "Unexpected origin push URLs: $($guardrailPushUrls -join ', ')" }

$guardrailOriginMainSymrefTargets = @(git -C $guardrailRepo symbolic-ref --quiet $guardrailOriginMainRef)
$guardrailOriginMainSymrefExit = $LASTEXITCODE
if ($guardrailOriginMainSymrefExit -eq 0) {
    if ($guardrailOriginMainSymrefTargets.Count -ne 1) { throw "Unexpected origin/main symref target count" }
    throw "Exact origin/main is symbolic; refusing to update referent: $($guardrailOriginMainSymrefTargets[0])"
} elseif ($guardrailOriginMainSymrefExit -eq 1) {
    if ($guardrailOriginMainSymrefTargets.Count -ne 0) { throw "Unexpected output while checking non-symbolic origin/main" }
} else {
    throw "Unable to inspect exact origin/main symbolic state"
}
$guardrailObservedOriginMainOids = @(git -C $guardrailRepo rev-parse --verify --quiet $guardrailOriginMainRef)
if ($LASTEXITCODE -ne 0 -or $guardrailObservedOriginMainOids.Count -ne 1) { throw "Exact direct origin/main ref is missing or unreadable" }
$guardrailObservedOriginMainOid = $guardrailObservedOriginMainOids[0]
Assert-GuardrailFullOid $guardrailObservedOriginMainOid "observed origin/main"

git -C $guardrailRepo fetch --no-tags --no-prune $guardrailExpectedOrigin refs/heads/main
if ($LASTEXITCODE -ne 0) { throw "Exact origin/main fetch failed" }
$guardrailFetchedMainOids = @(git -C $guardrailRepo rev-parse --verify "FETCH_HEAD^{commit}")
if ($LASTEXITCODE -ne 0 -or $guardrailFetchedMainOids.Count -ne 1) { throw "Unable to resolve fetched main commit" }
$guardrailFetchedMainOid = $guardrailFetchedMainOids[0]
Assert-GuardrailFullOid $guardrailFetchedMainOid "fetched main"
git -C $guardrailRepo update-ref --no-deref $guardrailOriginMainRef $guardrailFetchedMainOid $guardrailObservedOriginMainOid
if ($LASTEXITCODE -ne 0) { throw "Concurrent-safe exact origin/main update failed" }
$guardrailRemainingOriginMainSymrefTargets = @(git -C $guardrailRepo symbolic-ref --quiet $guardrailOriginMainRef)
$guardrailRemainingOriginMainSymrefExit = $LASTEXITCODE
if ($guardrailRemainingOriginMainSymrefExit -eq 0) {
    if ($guardrailRemainingOriginMainSymrefTargets.Count -ne 1) { throw "Unexpected remaining origin/main symref target count" }
    throw "Exact origin/main became symbolic: $($guardrailRemainingOriginMainSymrefTargets[0])"
} elseif ($guardrailRemainingOriginMainSymrefExit -eq 1) {
    if ($guardrailRemainingOriginMainSymrefTargets.Count -ne 0) { throw "Unexpected output while asserting direct origin/main" }
} else {
    throw "Unable to assert origin/main symbolic-ref absence"
}
$guardrailOriginMainOids = @(git -C $guardrailRepo show-ref --verify --hash $guardrailOriginMainRef)
if ($LASTEXITCODE -ne 0 -or $guardrailOriginMainOids.Count -ne 1) { throw "Unable to verify exact direct origin/main ref" }
$guardrailOriginMainOid = $guardrailOriginMainOids[0]
Assert-GuardrailFullOid $guardrailOriginMainOid "origin/main"
if ($guardrailOriginMainOid -ne $guardrailFetchedMainOid) { throw "Exact origin/main does not equal fetched main" }
Assert-GuardrailMainExactAndClean $guardrailOriginMainOid

$guardrailWorktreeRootPath = [IO.Path]::GetFullPath((Join-Path $guardrailRepo ".worktrees"))
$guardrailWorktreePath = [IO.Path]::GetFullPath((Join-Path $guardrailWorktreeRootPath "maintenance-guardrails"))
$guardrailWorktreeRootItem = Get-Item -LiteralPath $guardrailWorktreeRootPath -Force
if (-not $guardrailWorktreeRootItem.PSIsContainer -or ($guardrailWorktreeRootItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw ".worktrees is not an ordinary directory" }
if (-not $guardrailWorktreeRootItem.FullName.Equals($guardrailWorktreeRootPath, [StringComparison]::OrdinalIgnoreCase)) { throw "Unexpected .worktrees root" }
$guardrailWorktreeItem = Get-Item -LiteralPath $guardrailWorktreePath -Force
if (-not $guardrailWorktreeItem.PSIsContainer -or ($guardrailWorktreeItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Implementation worktree is not an ordinary directory" }
if (-not $guardrailWorktreeItem.FullName.Equals($guardrailWorktreePath, [StringComparison]::OrdinalIgnoreCase)) { throw "Unexpected implementation worktree path" }
if (-not $guardrailWorktreeItem.Parent.FullName.Equals($guardrailWorktreeRootPath, [StringComparison]::OrdinalIgnoreCase)) { throw "Implementation worktree escaped exact root" }

$guardrailRegisteredWorktrees = @(Get-GuardrailWorktreeRecords)
$guardrailRegisteredMatch = @($guardrailRegisteredWorktrees | Where-Object { [IO.Path]::GetFullPath($_.Path).Equals($guardrailWorktreePath, [StringComparison]::OrdinalIgnoreCase) })
if ($guardrailRegisteredMatch.Count -ne 1) { throw "Expected one exact registered implementation worktree" }
if ($guardrailRegisteredMatch[0].Branch -ne $guardrailWorktreeBranchRef) { throw "Implementation worktree is attached to an unexpected branch" }
Assert-GuardrailFullOid $guardrailRegisteredMatch[0].Head "registered worktree HEAD"
$guardrailWorktreeTopLevels = @(git -C $guardrailWorktreePath rev-parse --show-toplevel)
if ($LASTEXITCODE -ne 0 -or $guardrailWorktreeTopLevels.Count -ne 1) { throw "Unable to resolve worktree top level" }
if (-not [IO.Path]::GetFullPath($guardrailWorktreeTopLevels[0]).Equals($guardrailWorktreePath, [StringComparison]::OrdinalIgnoreCase)) { throw "Worktree top level is not the exact registered path" }
$guardrailAttachedRefs = @(git -C $guardrailWorktreePath symbolic-ref --quiet HEAD)
if ($LASTEXITCODE -ne 0 -or $guardrailAttachedRefs.Count -ne 1 -or $guardrailAttachedRefs[0] -ne $guardrailWorktreeBranchRef) { throw "Implementation worktree is not attached to the exact branch" }
$guardrailWorktreeOids = @(git -C $guardrailWorktreePath rev-parse --verify "HEAD^{commit}")
if ($LASTEXITCODE -ne 0 -or $guardrailWorktreeOids.Count -ne 1) { throw "Unable to capture implementation worktree HEAD" }
$guardrailWorktreeOid = $guardrailWorktreeOids[0]
Assert-GuardrailFullOid $guardrailWorktreeOid "implementation worktree HEAD"
if ($guardrailWorktreeOid -ne $guardrailRegisteredMatch[0].Head) { throw "Registered and actual worktree HEAD differ" }
git -C $guardrailRepo merge-base --is-ancestor $guardrailWorktreeOid $guardrailOriginMainOid
if ($LASTEXITCODE -eq 1) { throw "Implementation worktree HEAD is not merged into exact origin/main" }
if ($LASTEXITCODE -ne 0) { throw "Unable to verify implementation worktree ancestry" }

$guardrailTrackedStatus = @(git -C $guardrailWorktreePath status --porcelain=v1 --untracked-files=no)
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect tracked worktree status" }
if ($guardrailTrackedStatus.Count -ne 0) { throw "Implementation worktree has tracked changes" }
$guardrailUntrackedPaths = @(git -C $guardrailWorktreePath ls-files --others --exclude-standard)
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect untracked worktree paths" }
if ($guardrailUntrackedPaths.Count -ne 0) { throw "Unexpected untracked worktree paths: $($guardrailUntrackedPaths -join ', ')" }
$guardrailIgnoredPaths = @(git -C $guardrailWorktreePath ls-files --others --ignored --exclude-standard)
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect ignored worktree paths" }
$guardrailAllowedIgnoredExact = @(".superpowers/sdd/.gitignore")
$guardrailAllowedIgnoredPrefixes = @(
    ".superpowers/sdd/2026-08-30-maintenance-guardrails/",
    ".pytest_cache/",
    "__pycache__/",
    "eval/__pycache__/",
    "tests/__pycache__/"
)
foreach ($guardrailIgnoredPath in $guardrailIgnoredPaths) {
    if ([IO.Path]::IsPathRooted($guardrailIgnoredPath)) { throw "Ignored path is unexpectedly rooted: $guardrailIgnoredPath" }
    $guardrailIgnoredAllowed = $guardrailIgnoredPath -in $guardrailAllowedIgnoredExact
    foreach ($guardrailAllowedPrefix in $guardrailAllowedIgnoredPrefixes) {
        if ($guardrailIgnoredPath.StartsWith($guardrailAllowedPrefix, [StringComparison]::Ordinal)) { $guardrailIgnoredAllowed = $true }
    }
    if (-not $guardrailIgnoredAllowed) { throw "Unexpected ignored worktree path: $guardrailIgnoredPath" }
}

$guardrailRemoteRefLines = @(git -C $guardrailRepo ls-remote --heads $guardrailExpectedOrigin $guardrailRemoteBranchRef)
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect exact remote maintenance ref" }
if ($guardrailRemoteRefLines.Count -gt 1) { throw "Expected at most one exact remote maintenance ref" }
if ($guardrailRemoteRefLines.Count -eq 1) {
    $guardrailRemoteRefParts = $guardrailRemoteRefLines[0] -split '\s+', 2
    if ($guardrailRemoteRefParts.Count -ne 2 -or $guardrailRemoteRefParts[1] -ne $guardrailRemoteBranchRef) { throw "Unexpected remote ref: $($guardrailRemoteRefLines[0])" }
    $guardrailRemoteOid = $guardrailRemoteRefParts[0]
    Assert-GuardrailFullOid $guardrailRemoteOid "remote maintenance branch"
    if ($guardrailRemoteOid -ne $guardrailWorktreeOid) { throw "Remote maintenance OID does not match the validated local implementation HEAD" }
    git -C $guardrailRepo cat-file -e "$guardrailRemoteOid`^{commit}"
    if ($LASTEXITCODE -ne 0) { throw "Remote maintenance OID is not available as a local commit" }
    git -C $guardrailRepo merge-base --is-ancestor $guardrailRemoteOid $guardrailOriginMainOid
    if ($LASTEXITCODE -eq 1) { throw "Remote maintenance OID is not merged into exact origin/main" }
    if ($LASTEXITCODE -ne 0) { throw "Unable to verify remote maintenance ancestry" }
    git -C $guardrailRepo push "--force-with-lease=$guardrailRemoteBranchRef`:$guardrailRemoteOid" $guardrailExpectedOrigin ":$guardrailRemoteBranchRef"
    if ($LASTEXITCODE -ne 0) { throw "Leased exact remote maintenance deletion failed" }
} else {
    "remote maintenance/guardrails already absent; no push sent"
}

$guardrailRemoteRefLines = @(git -C $guardrailRepo ls-remote --heads $guardrailExpectedOrigin $guardrailRemoteBranchRef)
if ($LASTEXITCODE -ne 0) { throw "Unable to recheck exact remote maintenance ref" }
if ($guardrailRemoteRefLines.Count -ne 0) { throw "Remote maintenance branch still exists" }
$guardrailTrackingSymrefTargets = @(git -C $guardrailRepo symbolic-ref --quiet $guardrailTrackingBranchRef)
$guardrailTrackingSymrefExit = $LASTEXITCODE
if ($guardrailTrackingSymrefExit -eq 0) {
    if ($guardrailTrackingSymrefTargets.Count -ne 1) { throw "Unexpected tracking symref target count" }
    throw "Exact maintenance tracking ref is symbolic; refusing to delete referent: $($guardrailTrackingSymrefTargets[0])"
} elseif ($guardrailTrackingSymrefExit -eq 1) {
    if ($guardrailTrackingSymrefTargets.Count -ne 0) { throw "Unexpected output while checking non-symbolic tracking ref" }
} else {
    throw "Unable to inspect exact tracking ref symbolic state"
}
$guardrailTrackingOids = @(git -C $guardrailRepo rev-parse --verify --quiet $guardrailTrackingBranchRef)
$guardrailTrackingExit = $LASTEXITCODE
if ($guardrailTrackingExit -eq 0) {
    if ($guardrailTrackingOids.Count -ne 1) { throw "Unexpected tracking-ref OID count" }
    $guardrailTrackingOid = $guardrailTrackingOids[0]
    Assert-GuardrailFullOid $guardrailTrackingOid "origin maintenance tracking ref"
    git -C $guardrailRepo update-ref --no-deref -d $guardrailTrackingBranchRef $guardrailTrackingOid
    if ($LASTEXITCODE -ne 0) { throw "Compare-and-delete of exact tracking ref failed" }
} elseif ($guardrailTrackingExit -ne 1) {
    throw "Unable to inspect exact tracking ref"
} else {
    "origin/maintenance/guardrails tracking ref already absent"
}
$guardrailRemainingSymrefTargets = @(git -C $guardrailRepo symbolic-ref --quiet $guardrailTrackingBranchRef)
$guardrailRemainingSymrefExit = $LASTEXITCODE
if ($guardrailRemainingSymrefExit -eq 0) {
    if ($guardrailRemainingSymrefTargets.Count -ne 1) { throw "Unexpected remaining tracking symref target count" }
    throw "Exact maintenance tracking ref still exists as a symbolic ref: $($guardrailRemainingSymrefTargets[0])"
} elseif ($guardrailRemainingSymrefExit -eq 1) {
    if ($guardrailRemainingSymrefTargets.Count -ne 0) { throw "Unexpected output while asserting symbolic-ref absence" }
} else {
    throw "Unable to assert exact symbolic-ref absence"
}
git -C $guardrailRepo show-ref --verify --quiet $guardrailTrackingBranchRef
$guardrailRemainingDirectExit = $LASTEXITCODE
if ($guardrailRemainingDirectExit -eq 0) {
    throw "Exact maintenance tracking ref still exists as a direct ref"
} elseif ($guardrailRemainingDirectExit -eq 1) {
    "exact direct maintenance tracking ref absent"
} else {
    throw "Unable to assert exact direct-ref absence"
}

$guardrailDisposableDirectories = @(
    (Join-Path $guardrailWorktreePath ".superpowers\sdd\2026-08-30-maintenance-guardrails"),
    (Join-Path $guardrailWorktreePath ".pytest_cache"),
    (Join-Path $guardrailWorktreePath "__pycache__"),
    (Join-Path $guardrailWorktreePath "eval\__pycache__"),
    (Join-Path $guardrailWorktreePath "tests\__pycache__")
)
foreach ($guardrailDisposableDirectory in $guardrailDisposableDirectories) {
    Remove-GuardrailDisposableDirectory $guardrailDisposableDirectory $guardrailWorktreePath
}
$guardrailSddIgnorePath = [IO.Path]::GetFullPath((Join-Path $guardrailWorktreePath ".superpowers\sdd\.gitignore"))
if (-not $guardrailSddIgnorePath.StartsWith($guardrailWorktreePath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "SDD ignore marker escaped worktree" }
if (Test-Path -LiteralPath $guardrailSddIgnorePath) {
    $guardrailSddIgnoreItem = Get-Item -LiteralPath $guardrailSddIgnorePath -Force
    if ($guardrailSddIgnoreItem.PSIsContainer -or ($guardrailSddIgnoreItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "SDD ignore marker is not an ordinary file" }
    $guardrailSddIgnoreAncestor = $guardrailSddIgnoreItem.Parent
    while (-not $guardrailSddIgnoreAncestor.FullName.Equals($guardrailWorktreePath, [StringComparison]::OrdinalIgnoreCase)) {
        if ($guardrailSddIgnoreAncestor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point in SDD ignore-marker ancestry: $($guardrailSddIgnoreAncestor.FullName)" }
        $guardrailSddIgnoreAncestor = $guardrailSddIgnoreAncestor.Parent
        if ($null -eq $guardrailSddIgnoreAncestor) { throw "SDD ignore marker escaped worktree ancestry" }
    }
    if ((Get-Content -LiteralPath $guardrailSddIgnorePath -Raw).Trim() -ne "*") { throw "Unexpected SDD ignore marker content" }
    Remove-Item -LiteralPath $guardrailSddIgnorePath
    if (Test-Path -LiteralPath $guardrailSddIgnorePath) { throw "SDD ignore marker removal failed" }
}

$guardrailFinalWorktreeStatus = @(git -C $guardrailWorktreePath status --porcelain=v1 --untracked-files=all --ignored=matching)
if ($LASTEXITCODE -ne 0) { throw "Unable to perform final comprehensive worktree status" }
if ($guardrailFinalWorktreeStatus.Count -ne 0) { throw "Worktree still has tracked, untracked, or ignored entries: $($guardrailFinalWorktreeStatus -join ', ')" }
git -C $guardrailRepo worktree remove $guardrailWorktreePath
if ($LASTEXITCODE -ne 0) { throw "Non-force exact worktree removal failed" }
if (Test-Path -LiteralPath $guardrailWorktreePath) { throw "Exact implementation worktree path still exists" }
$guardrailRegisteredWorktrees = @(Get-GuardrailWorktreeRecords)
$guardrailRegisteredMatch = @($guardrailRegisteredWorktrees | Where-Object { [IO.Path]::GetFullPath($_.Path).Equals($guardrailWorktreePath, [StringComparison]::OrdinalIgnoreCase) })
if ($guardrailRegisteredMatch.Count -ne 0) { throw "Exact implementation worktree is still registered" }

git -C $guardrailRepo branch -d -- maintenance/guardrails
if ($LASTEXITCODE -ne 0) { throw "Safe deletion of local maintenance branch failed" }
git -C $guardrailRepo branch -d -- docs/maintenance-guardrails-spec
if ($LASTEXITCODE -ne 0) { throw "Safe deletion of local planning branch failed" }
foreach ($guardrailDeletedBranchRef in @($guardrailWorktreeBranchRef, $guardrailPlanningBranchRef)) {
    git -C $guardrailRepo show-ref --verify --quiet $guardrailDeletedBranchRef
    if ($LASTEXITCODE -eq 0) { throw "Exact local branch still exists: $guardrailDeletedBranchRef" }
    if ($LASTEXITCODE -ne 1) { throw "Unable to assert local branch absence: $guardrailDeletedBranchRef" }
}

Assert-GuardrailMainExactAndClean $guardrailOriginMainOid
"exact maintenance cleanup verified"
~~~

The `-d` forms must remain lowercase so Git refuses to delete an unmerged
branch. Do not replace the exact commands with wildcard ref deletion, broad
fetch/prune or worktree prune, `git clean`, forced worktree removal,
`git branch -D`, globbed paths, or recursive deletion outside the explicitly
enumerated and boundary-checked disposable directories above.

Expected: main checkout remains at origin/main; no maintenance branches, user
files, or unrelated repositories are removed.

- [ ] **Step 5: Report the outcome**

Include:

- PR URL and exact merge SHA.
- Local and GitHub Actions test evidence.
- Exact branch-protection checks and enforcement flags.
- Vulnerability-alert, Dependabot security-update, secret-scanning, push-protection, branch-cleanup, and auto-merge states.
- Confirmation that v1.0.0 and both Hugging Face repositories were unchanged.
- A direct link to docs/MAINTENANCE.md.
- A clear statement that normal future work now requires a PR and no external reviewer.
