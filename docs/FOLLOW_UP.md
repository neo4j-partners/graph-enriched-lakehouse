# Supply Chain Security Follow-Up Proposal

## Goal

Make dependency updates and privileged CI workflows safer by turning the supply
chain controls in `docs/SECURITY_SUPPLY_CHAIN.md` into enforceable repository
policy.

## Assumptions

- The current PR handles urgent dependency fixes and the Pages workflow cleanup.
- Follow-up work should be reviewable as a separate PR because it changes
  dependency automation policy and CI behavior.
- The repository will keep using the package managers already present in each
  project: npm for slides, Bun for app frontends, and uv for Python projects.

## Risks

- Release-age quarantine may delay legitimate security patches unless an
  explicit override process exists.
- Expanding dependency automation can create noisy PRs if package roots are not
  grouped carefully.
- Pinning GitHub Actions by SHA improves integrity but increases maintenance
  overhead.
- CI enforcement must match each package manager, or builds may fail on valid
  lockfile changes.

## Phase Checklist

### Phase 1: Dependency Automation Coverage

Status: Pending

- Inventory every package root with a committed lockfile.
- Decide whether Renovate will replace Dependabot or run alongside Dependabot.
- Add dependency automation coverage for all npm, Bun, and uv package roots.
- Group related dependency updates by project area and ecosystem.
- Keep ignored or externally sourced dependencies documented.

Validation:

- Dependency automation opens test PRs for each intended ecosystem.
- No package root with a committed lockfile is missing from automation.

### Phase 2: Release-Age Quarantine

Status: Pending

- Configure a minimum release age for npm/Bun dependency updates.
- Configure an equivalent Python update policy where tooling supports it.
- Define the manual override path for urgent security fixes.
- Document when maintainers may bypass quarantine and what review is required.

Validation:

- Test dependency update PRs do not consume package versions younger than the
  configured quarantine window.
- The override path is documented in repository docs.

### Phase 3: Immutable Install Enforcement

Status: Pending

- Add CI checks that use immutable install commands for each package manager.
- Use `npm ci` for npm projects with `package-lock.json`.
- Use `bun install --frozen-lockfile` for Bun projects.
- Use `uv sync --locked` or `uv run --locked` for uv projects.
- Add audit or vulnerability checks where they are reliable and low noise.

Validation:

- CI fails if a package manifest and lockfile disagree.
- CI passes from a clean checkout with existing lockfiles.

### Phase 4: Privileged Workflow Hardening

Status: Pending

- Identify workflows that deploy, publish, or request elevated token scopes.
- Pin third-party GitHub Actions by full commit SHA in privileged workflows.
- Keep permissions scoped to the job that needs them.
- Confirm privileged jobs only run from trusted branches, tags, or protected
  environments.

Validation:

- Privileged workflows have job-level permissions.
- Publish or deploy jobs do not run untrusted pull request code.
- Third-party Actions in privileged workflows are SHA-pinned or explicitly
  accepted as tag-pinned with a documented rationale.

## Completion Criteria

- Every package root with a lockfile has dependency automation coverage or a
  documented exclusion.
- CI enforces immutable installs for npm, Bun, and uv package roots.
- Dependency automation includes release-age quarantine or a documented reason
  why it cannot for a given ecosystem.
- Privileged workflows use narrow permissions and reviewed Action pinning.
- Repository documentation describes the security patch override process.
