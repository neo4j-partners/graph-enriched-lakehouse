# Proposal: Automate Analyst Client UI Testing

Research date: May 10, 2026

Implementation status: Phases 1-4 are implemented for `analyst-client`. Phase 5 remains optional and is not part of the default PR gate.

## Goal

Add reliable browser-level UI tests for `analyst-client` using Playwright and pytest so the core analyst workflow can be validated locally and in CI before deployment.

The first target should be the mock backend path. It is deterministic, does not require Neo4j or Databricks credentials, and covers the highest-value browser behavior: search, select rings, load to lakehouse, ask Genie, and export the report modal.

## Recommendation

Use the Python Playwright stack:

- `pytest`
- `pytest-playwright`
- `playwright`
- `uv` dependency groups for test-only dependencies

This keeps the test toolchain aligned with the Flask app and avoids adding a Node test stack just for UI automation. The official Playwright Python docs recommend the pytest plugin for end-to-end tests because it provides Playwright fixtures, browser contexts, and multi-browser options out of the box.

The default suite should install and run Chromium only:

```bash
cd analyst-client
uv sync --group dev
uv run python -m playwright install chromium
uv run pytest tests --browser chromium --tracing retain-on-failure --screenshot only-on-failure
```

CI can use the same commands. Linux runners may need Playwright system dependencies, so the CI command should use `uv run python -m playwright install --with-deps chromium` unless the runner image already includes them.

## Background: Playwright Best Practices

The official Playwright guidance is a good match for this app:

- Test user-visible behavior, not implementation details. For this app, tests should interact with visible workflow controls and assert rendered results instead of poking JavaScript state.
- Keep tests isolated. Each test should get a fresh browser context and should not depend on another test having already searched, loaded, or asked a question.
- Prefer Playwright locators over CSS and XPath selectors. Use role, text, label, and explicit test IDs where the UI does not expose a stable accessible name.
- Use web-first assertions. These automatically wait and retry until the expected UI state appears, which reduces timing flakes around async fetches and graph rendering.
- Use trace artifacts for CI debugging. Playwright traces include actions, DOM snapshots, console output, network requests, and source locations, which are more useful than screenshots alone.
- Avoid real third-party systems in the core UI suite. The daily fast suite should run against `USE_MOCK_BACKEND=true`; real Neo4j and Databricks checks should be a separate opt-in suite.
- Install only the browser needed for fast CI at first. Chromium is enough for a smoke suite; cross-browser coverage can be added once the core test harness is stable.

## Current App Fit

`analyst-client` already has the right shape for UI automation:

- It can run locally with `uv run python app.py`.
- It supports `USE_MOCK_BACKEND=true`, which avoids external credentials.
- It has meaningful element IDs in the current frontend, such as `search-form`, `load-btn`, `ask-form`, `ask-input`, and `export-btn`.
- It has stable API outcomes in mock mode, including known ring IDs and a known Genie mock answer.

The main gap is selector durability. The existing IDs are usable, but the proposal should add a few `data-testid` attributes to controls and assertions that are important to the test contract. That makes tests less brittle when copy, layout, or CSS changes.

One operational gap should be handled before making UI tests a required CI gate: the page currently loads Cytoscape from a CDN. That is fine for manual demos, but it makes a headless browser test depend on external network availability. The preferred fix is to vendor the Cytoscape asset or serve it through the Flask app so the deterministic mock UI suite has no third-party runtime dependency.

## Proposed Test Coverage

Phase 1 should cover one complete mock analyst journey:

- Open the app homepage.
- Confirm the search screen is visible.
- Submit a fraud ring search.
- Verify the results panel appears and known ring IDs are present.
- Select `RING-0041` and `RING-0087`.
- Click `Load Selected to Lakehouse`.
- Verify the load screen shows expected mock counts and quality checks.
- Continue to analysis.
- Ask “Which accounts have the highest risk scores?”
- Verify the mock Genie answer and result table render.
- Open the export report modal.
- Verify the report includes selected rings and high-risk account content.

Phase 2 should add focused UI regression checks:

- Search controls render with default values.
- Load button remains disabled until at least one ring is selected.
- Back navigation preserves expected workflow state.
- Export button only appears after the first Genie response.
- Console errors and failed network responses fail the test.

Phase 3 should add optional real-backend smoke coverage:

- Run only when explicit environment variables are present.
- Use `USE_MOCK_BACKEND=false`.
- Validate that the page can search and that `/api/search` returns at least one result.
- Skip by default in CI to avoid credential, cost, and data availability flakes.

## Proposed File Layout

Add the following under `analyst-client`:

- `tests/conftest.py`: starts and stops the Flask app on an unused local port in mock mode.
- `tests/test_ui_mock_flow.py`: covers the complete mock analyst workflow.
- `tests/test_ui_contract.py`: covers smaller workflow and selector contracts.
- `test-results/`: ignored artifact output for Playwright traces, screenshots, and failure details.

Add or update project metadata:

- `pyproject.toml`: add a `dev` dependency group for pytest and Playwright.
- `.gitignore`: ensure Playwright artifacts are ignored if not already covered.
- `README.md`: add local UI test commands and artifact viewing notes.

Recommended dev dependency group:

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "playwright>=1.50",
    "pytest-playwright>=0.7",
]
```

## Phase Checklist

### Phase 1: Foundation

Status: Implemented

Checklist:

- Add Playwright and pytest dev dependencies through `uv`.
- Add `tests/conftest.py` with a server fixture that starts `analyst-client` in mock mode on a free port.
- Ensure the fixture forces `USE_MOCK_BACKEND=true` and overrides any `.env` values that could point to real services.
- Add a browser page fixture that uses the server base URL.
- Add trace and screenshot artifact defaults for failed tests.

Validation:

- `uv sync --group dev` succeeds.
- `uv run pytest --collect-only` discovers the UI tests.
- The Flask process is stopped after the test run.
- Running the tests does not require Neo4j, Databricks, or any secret-bearing environment variable.

### Phase 2: Selector Hardening

Status: Implemented

Checklist:

- Add `data-testid` attributes to stable workflow elements in `static/index.html`.
- Prefer accessible role/text locators where they are natural and stable.
- Use `data-testid` for repeated or ambiguous controls such as result checkboxes, graph containers, and modal buttons.
- Avoid selectors tied to CSS classes, DOM depth, or visual layout.
- Keep `data-testid` values named after business intent, such as `ring-checkbox-RING-0041`, `load-selected`, and `report-modal`, rather than visual position.

Validation:

- Existing manual browser workflow still works.
- Playwright locators uniquely identify target elements.

### Phase 3: Mock Workflow Test

Status: Implemented

Checklist:

- Implement the full search-to-report workflow test.
- Assert known mock values rather than only checking that elements exist.
- Fail on browser console errors and failed application network responses.
- Ignore expected third-party or browser noise only through an explicit allowlist with comments.
- Capture a trace on failure.

Validation:

- `uv run pytest tests/test_ui_mock_flow.py --browser chromium --tracing retain-on-failure` passes locally.
- `test-results/` contains useful artifacts when a test is intentionally failed.

### Phase 4: CI Integration

Status: Implemented

Checklist:

- Add a CI job that installs Python dependencies with `uv`.
- Install Chromium for Playwright before running tests.
- Run the UI suite in headless Chromium.
- Upload `test-results/` artifacts on failure.
- Keep workers conservative in CI for stability.
- Scope CI triggers to `analyst-client/**`, shared deployment files, and the UI test workflow file unless a broader repository gate is desired.

Validation:

- CI runs the UI suite on every pull request touching `analyst-client`.
- Failed runs expose trace artifacts for local replay.
- Replaying an uploaded trace with `uv run python -m playwright show-trace <trace.zip>` works from a local checkout.

### Phase 5: Optional Real-Backend Smoke Test

Status: Pending

Checklist:

- Add a separate pytest marker for real-backend tests.
- Require explicit environment variables before running.
- Keep assertions shallow: app boots, search completes, and at least one result appears.
- Do not include this suite in the default PR gate.

Validation:

- Real-backend smoke test skips cleanly when credentials are absent.
- Real-backend smoke test can be run manually from a configured developer machine.

## Quality Bar

The UI suite should be considered ready when:

- The default test path is deterministic and does not require secrets.
- Tests exercise behavior through the browser rather than direct API calls.
- Locators are resilient to layout and CSS changes.
- Assertions wait for visible browser outcomes instead of sleeping.
- Failure output includes enough trace detail to debug without reproducing locally.
- Local test commands and CI behavior are documented.

## Risks and Mitigations

- Risk: Tests become flaky because Cytoscape rendering is async.
  Mitigation: Assert surrounding UI state and stable data rather than low-level canvas/SVG internals unless graph rendering itself becomes the target.

- Risk: Tests fail in CI because the browser cannot fetch the Cytoscape CDN asset.
  Mitigation: Vendor Cytoscape or serve it locally through Flask before making the suite mandatory.

- Risk: Real-backend tests fail due to credentials, data drift, or workspace availability.
  Mitigation: Keep real-backend checks opt-in and separate from the default mock UI suite.

- Risk: Selectors break during UI copy changes.
  Mitigation: Use accessible locators for user-visible contracts and `data-testid` for controls where copy is not part of the contract.

- Risk: CI is slow because Playwright installs every browser.
  Mitigation: Start with Chromium only. Add Firefox/WebKit only if browser-specific defects matter for this app.

## Open Decisions

- Whether to gate every pull request with the full mock UI workflow or only changes under `analyst-client`.
- Whether CI should use a Playwright Python Docker image or install Chromium into the existing Python runner.
- Whether visual regression testing is in scope. This proposal does not include screenshots as golden images because the first priority is workflow correctness.

## References

- [Playwright Best Practices](https://playwright.dev/docs/best-practices): user-visible behavior, isolated tests, resilient locators, web-first assertions, tracing, CI, and browser strategy.
- [Playwright Python Pytest Plugin Reference](https://playwright.dev/python/docs/test-runners): pytest fixtures, browser/context/page lifecycle, CLI options, base URL support, screenshots, video, and tracing.
- [Playwright Python Trace Viewer](https://playwright.dev/python/docs/trace-viewer): trace recording, local trace viewing, DOM snapshots, console logs, network logs, and failure debugging.
- [Playwright Python Continuous Integration](https://playwright.dev/python/docs/ci): Python CI setup, browser installation, Docker image option, artifact upload, and browser cache guidance.
- [pytest documentation](https://docs.pytest.org/en/stable/): pytest runner, fixtures, markers, and test organization.
