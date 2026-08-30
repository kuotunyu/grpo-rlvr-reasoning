# Maintenance Guardrails Design

## Context

`kuotunyu/grpo-rlvr-reasoning` is public and has an audited `v1.0.0`
release, three-version Python CI, a scheduled public-release audit, secret
scanning, and secret-scanning push protection. The repository currently has no
branch protection or ruleset. Vulnerability alerts and Dependabot security
updates are disabled, and future GitHub Actions updates are not monitored.

The repository is maintained by one person. The guardrails must prevent
high-impact mistakes without requiring an external reviewer or creating a
recovery process that is harder than the mistake it prevents.

## Goals

- Prevent direct, forced, or destructive changes to `main`, including changes
  made with administrator privileges.
- Require the existing Python 3.10, 3.11, and 3.12 test jobs before merge.
- Preserve a solo-maintainer path: no human approval is required after CI
  succeeds.
- Make normal changes, releases, Hugging Face updates, and failure recovery
  understandable from one short maintainer guide.
- Enable low-noise dependency and vulnerability monitoring.
- Apply and verify remote settings without destructive test pushes.

## Non-goals

- No new model training or GPU evaluation.
- No new release tag or changes to the existing `v1.0.0` release.
- No modification of either Hugging Face repository.
- No change to MDCP, vision-active-learning-loop, myair, tw-labor-law-rag,
  coding-agent-eval, Edge, MVTec, or any other repository.
- No required external reviewer, CODEOWNERS gate, signed-commit requirement,
  merge queue, or automatic PR merge.
- No Python dependency updater until the repository has a committed Python
  dependency manifest. The current workflows intentionally install only
  `pytest` and use dependency-free release tooling.

## Selected Approach

Use classic branch protection with a pull-request requirement and zero required
approving reviews. This is the strictest configuration that still works for a
single maintainer. Pair it with grouped weekly GitHub Actions updates, security
alerts, automatic deletion of merged branches, and a single maintainer guide.

Alternatives were rejected as follows:

- Requiring one or more approvals would prevent the sole maintainer from
  completing routine work without another account.
- Allowing direct pushes while merely reporting CI failures would not prevent
  the mistake this work is meant to stop.
- Signed commits, CODEOWNERS, merge queues, and broad repository rulesets add
  operational complexity without a current collaborator or compliance need.

## Repository Changes

### `.github/dependabot.yml`

Create a Dependabot version-2 configuration for the `github-actions` ecosystem
at directory `/`. It will run every Monday at 09:00 in `Asia/Taipei`, group all
GitHub Actions updates into one PR, use a `ci` commit-message prefix, and limit
open version-update PRs to three.

Security updates may still appear separately when GitHub considers them urgent;
they must pass the same protected-branch CI before merge.

### `docs/MAINTENANCE.md`

Create one concise, Traditional Chinese maintainer guide with these sections:

1. **Default rule** — describe the desired change to Codex; do not manually
   force-push, delete release tags, rewrite history, or overwrite HF repos.
2. **Normal repository change** — branch, commit, push, PR, wait for three
   required CI jobs, resolve conversations, then merge.
3. **GitHub release** — run the local test suite, result verifier, and live
   release auditor; push through a PR; wait for main CI; create a new immutable
   version number rather than moving an existing tag.
4. **Hugging Face change** — use a candidate PR, audit the candidate revision,
   request review, merge only after approval, and rerun the live audit. Never
   direct-write, delete, or rewrite the remote default branch.
5. **When checks fail** — do not bypass protection. Preserve the failing output
   and ask Codex to diagnose it.
6. **Recovery** — revert with a new PR. Never repair public history with a
   force-push.

The guide will distinguish required steps from optional improvements and keep
all copy-paste commands read-only or safe by default.

### `README.md`

Add one visible link to `docs/MAINTENANCE.md` near the verification or license
sections. The README remains the project overview; the maintenance guide is the
only operational source of truth.

### Repository-health tests

Extend the existing dependency-free tests to verify:

- `.github/dependabot.yml` exists and contains the approved ecosystem,
  schedule, timezone, group, PR limit, and commit prefix.
- `README.md` links to `docs/MAINTENANCE.md`.
- The maintainer guide contains the normal, release, HF, failure, and recovery
  sections plus the explicit prohibitions on force-push and direct HF writes.

The tests will not add PyYAML or another runtime dependency. They will validate
the small, intentionally fixed configuration as text, while a separate local
YAML parse check will run before publication.

## GitHub Remote Settings

After the repository changes are merged and green on `main`, apply classic
branch protection to `main` with the following exact behavior:

- `required_status_checks.strict = true`
- Required checks:
  - `pytest (3.10)`
  - `pytest (3.11)`
  - `pytest (3.12)`
- `enforce_admins = true`
- Pull requests required with `required_approving_review_count = 0`
- Code-owner review disabled
- Last-push approval disabled
- Stale-review dismissal disabled because approvals are not required
- Conversation resolution required
- Linear history not required
- Force pushes disabled
- Branch deletion disabled
- Branch locking disabled
- Push restrictions omitted for this personal repository

Do not require the `public release audit` workflow on every PR. That workflow is
scheduled and path-filtered, so it is not guaranteed to create a check for every
change. It remains a publication-health signal and runs when its monitored files
change on `main`.

Also apply these repository settings:

- Enable vulnerability alerts.
- Enable Dependabot security updates.
- Keep secret scanning and push protection enabled.
- Enable automatic deletion of source branches after merge.
- Keep automatic merge disabled so a person must make the final merge decision.

The zero-review PR configuration is supported by GitHub's current protected
branch API, which accepts `required_approving_review_count = 0`. The Dependabot
configuration follows GitHub's documented `github-actions` ecosystem and root
directory convention:

- <https://docs.github.com/en/rest/branches/branch-protection>
- <https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-version-updates>

## Sequencing and Data Flow

1. Create the repository files and tests on an isolated maintenance branch.
2. Run the full local test suite, result verifier, compile check, YAML parse, and
   live release audit.
3. Push the branch and open a PR while `main` is still unprotected.
4. Wait for all three CI matrix jobs and any applicable release audit to pass.
5. Merge the PR and verify the exact commit on `main` is green.
6. Enable vulnerability alerts, Dependabot security updates, and merged-branch
   deletion.
7. Apply branch protection last.
8. Read all settings back through the GitHub API and compare them with this
   specification.

Applying branch protection last prevents a partially configured rule from
blocking the PR that installs its own documentation and tests.

## Failure Handling and Rollback

- If local tests or PR checks fail, stop before remote settings are changed.
- If a security endpoint is unavailable, leave the existing security settings
  untouched and report the precise API response.
- If branch protection validation fails, immediately restore the previously
  observed unprotected state rather than leaving a partial configuration.
- Do not test protection by attempting a direct push to `main`. API read-back is
  sufficient and does not risk creating an unwanted commit.
- Do not alter or delete `v1.0.0` during rollback.

## Acceptance Criteria

- Repository tests pass on Python 3.10, 3.11, and 3.12.
- Result verification, compile checks, YAML parsing, and the live release audit
  pass locally.
- The maintenance PR and exact merged `main` commit pass all CI jobs.
- The GitHub API reports the three exact required checks, strict status checks,
  administrator enforcement, zero approving reviews, required conversation
  resolution, and disabled force-push/deletion.
- Vulnerability alerts and Dependabot security updates report enabled.
- Secret scanning and push protection remain enabled.
- Automatic deletion of merged branches is enabled and auto-merge remains
  disabled.
- The repository remains public and `v1.0.0` still targets
  `61eb57ccd0029f340d359d28700ee2bd50f47849`.
- No Hugging Face repository or out-of-scope local repository changes.
