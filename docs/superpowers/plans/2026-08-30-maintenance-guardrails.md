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
- Consumes: Existing ROOT constant and repository-health test conventions in tests/test_repository_health.py.
- Produces: A weekly grouped GitHub Actions update policy, a single maintainer guide, and dependency-free tests that define their required content.

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

- [ ] **Step 2: Write the failing repository-health tests**

Append these tests to tests/test_repository_health.py:

~~~python
def test_dependabot_github_actions_policy_is_pinned():
    text = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")

    required = (
        'version: 2',
        'package-ecosystem: "github-actions"',
        'directory: "/"',
        'interval: "weekly"',
        'day: "monday"',
        'time: "09:00"',
        'timezone: "Asia/Taipei"',
        'open-pull-requests-limit: 3',
        'prefix: "ci"',
        'patterns:',
        '- "*"',
    )
    assert all(fragment in text for fragment in required)
    assert text.count('package-ecosystem: "github-actions"') == 1


def test_maintenance_guide_is_the_documented_operator_entrypoint():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "MAINTENANCE.md").read_text(encoding="utf-8")

    assert "[維護與發布防呆指南](docs/MAINTENANCE.md)" in readme
    for heading in (
        "## 1. 預設做法",
        "## 2. 一般 GitHub 修改",
        "## 3. 發布 GitHub 版本",
        "## 4. 修改 Hugging Face",
        "## 5. 檢查失敗時",
        "## 6. 復原方式",
    ):
        assert heading in guide
    for prohibition in (
        "不要 force-push",
        "不要移動或重建既有 release tag",
        "不要直接寫入、刪除或重寫 HF default branch",
    ):
        assert prohibition in guide
~~~

- [ ] **Step 3: Run the focused tests and observe the expected failure**

Run:

~~~powershell
python -m pytest tests/test_repository_health.py -q
~~~

Expected: failures caused by the missing .github/dependabot.yml and docs/MAINTENANCE.md files.

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
python -c "import yaml, pathlib; data=yaml.safe_load(pathlib.Path('.github/dependabot.yml').read_text(encoding='utf-8')); assert data['version'] == 2; print('dependabot YAML parsed')"
~~~

Expected: dependabot YAML parsed.

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
$guardrailActionAppIds = @($guardrailCheckRuns.check_runs | Where-Object { $_.name -in $guardrailCheckNames } | ForEach-Object { $_.app.id } | Sort-Object -Unique)
if ($guardrailActionAppIds.Count -ne 1) { throw "Expected one GitHub Actions app id for all required checks" }
$guardrailActionsAppId = $guardrailActionAppIds[0]
$guardrailActionsAppId
~~~

Expected: one positive GitHub Actions app ID shared by all three checks.

- [ ] **Step 3: Build and apply the exact protection payload**

Run:

~~~powershell
$guardrailMergeSha = gh api repos/kuotunyu/grpo-rlvr-reasoning/commits/main --jq .sha
$guardrailCheckNames = @("pytest (3.10)", "pytest (3.11)", "pytest (3.12)")
$guardrailCheckRuns = gh api "repos/kuotunyu/grpo-rlvr-reasoning/commits/$guardrailMergeSha/check-runs?per_page=100" | ConvertFrom-Json
$guardrailActionAppIds = @($guardrailCheckRuns.check_runs | Where-Object { $_.name -in $guardrailCheckNames } | ForEach-Object { $_.app.id } | Sort-Object -Unique)
if ($guardrailActionAppIds.Count -ne 1) { throw "Expected one GitHub Actions app id for all required checks" }
$guardrailActionsAppId = $guardrailActionAppIds[0]
$guardrailRequiredChecks = @(
    @{ context = "pytest (3.10)"; app_id = $guardrailActionsAppId },
    @{ context = "pytest (3.11)"; app_id = $guardrailActionsAppId },
    @{ context = "pytest (3.12)"; app_id = $guardrailActionsAppId }
)
$guardrailProtectionPayload = @{
    required_status_checks = @{
        strict = $true
        contexts = @()
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
$guardrailCheckNames = @("pytest (3.10)", "pytest (3.11)", "pytest (3.12)")
$guardrailProtection = gh api repos/kuotunyu/grpo-rlvr-reasoning/branches/main/protection | ConvertFrom-Json
$guardrailActualChecks = @($guardrailProtection.required_status_checks.checks.context | Sort-Object)
$guardrailExpectedChecks = @($guardrailCheckNames | Sort-Object)
if (Compare-Object $guardrailExpectedChecks $guardrailActualChecks) { throw "Required checks do not match" }
if (-not $guardrailProtection.required_status_checks.strict) { throw "Strict checks are disabled" }
if (-not $guardrailProtection.enforce_admins.enabled) { throw "Admin enforcement is disabled" }
if ($guardrailProtection.required_pull_request_reviews.required_approving_review_count -ne 0) { throw "Review count is not zero" }
if ($guardrailProtection.required_pull_request_reviews.require_code_owner_reviews) { throw "Code-owner reviews are enabled" }
if ($guardrailProtection.required_pull_request_reviews.require_last_push_approval) { throw "Last-push approval is enabled" }
if (-not $guardrailProtection.required_conversation_resolution.enabled) { throw "Conversation resolution is disabled" }
if ($guardrailProtection.allow_force_pushes.enabled) { throw "Force pushes are enabled" }
if ($guardrailProtection.allow_deletions.enabled) { throw "Branch deletion is enabled" }
if ($guardrailProtection.required_linear_history.enabled) { throw "Linear history is unexpectedly required" }
if ($guardrailProtection.lock_branch.enabled) { throw "Main is unexpectedly locked" }
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

First confirm the PR is merged and origin/main contains its merge commit. Delete
only the exact remote maintenance/guardrails branch:

~~~powershell
git ls-remote --heads origin refs/heads/maintenance/guardrails
git push origin --delete maintenance/guardrails
~~~

Then resolve and verify that the implementation worktree path is under the
repository's .worktrees directory and that it is clean. Run:

~~~powershell
$guardrailRepo = "D:\AI-Portfolio\CC_github部隊\RL_Github\1_GRPORLVR_推理訓練"
$guardrailWorktreeRoot = Resolve-Path -LiteralPath "$guardrailRepo\.worktrees"
$guardrailWorktree = Resolve-Path -LiteralPath "$guardrailRepo\.worktrees\maintenance-guardrails"
if (-not $guardrailWorktree.Path.StartsWith($guardrailWorktreeRoot.Path + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "Worktree escaped intended root" }
if (git -C $guardrailWorktree.Path status --porcelain) { throw "Implementation worktree is not clean" }
git -C $guardrailRepo worktree remove "$($guardrailWorktree.Path)"
git -C $guardrailRepo worktree prune
git -C $guardrailRepo branch -d maintenance/guardrails
git -C $guardrailRepo branch -d docs/maintenance-guardrails-spec
git -C $guardrailRepo worktree list
git -C $guardrailRepo status --short
~~~

The -d form must remain lowercase so Git refuses to delete an unmerged branch.

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
