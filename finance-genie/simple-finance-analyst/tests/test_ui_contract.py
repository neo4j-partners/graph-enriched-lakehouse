from __future__ import annotations

from playwright.sync_api import Page, expect


def test_search_controls_and_load_button_contract(
    page: Page, base_url: str
) -> None:
    page.goto(base_url)

    expect(page.get_by_test_id("screen-search")).to_be_visible()
    expect(page.get_by_test_id("signal-fraud-rings")).to_be_visible()
    fraud_rings_radio = page.locator(
        'input[name="signal_type"][value="fraud_rings"]'
    )
    expect(fraud_rings_radio).to_be_checked()
    expect(page.get_by_test_id("load-selected")).not_to_be_visible()

    page.get_by_test_id("search-submit").click()

    expect(page.get_by_test_id("results-panel")).to_be_visible()
    expect(page.get_by_test_id("ring-count")).to_have_text("6 rings")
    expect(page.get_by_test_id("load-selected")).to_be_disabled()
    expect(page.get_by_test_id("selected-count")).to_have_text("0 selected")
    expect(page.get_by_test_id("select-all-rings")).not_to_be_checked()

    page.get_by_test_id("graph-help-button").focus()

    expect(page.get_by_test_id("graph-help-tooltip")).to_be_visible()
    expect(page.get_by_test_id("graph-help-tooltip")).to_contain_text(
        "Each card is one detected cluster"
    )
    expect(page.get_by_test_id("graph-help-tooltip")).to_contain_text(
        "Tight loops can indicate circular fund movement"
    )
    expect(page.get_by_test_id("graph-help-tooltip")).to_contain_text(
        "risk, hub count, density, volume, and shared identifiers"
    )
    expect(page.get_by_test_id("ring-card-RING-0041")).to_contain_text(
        "Hub-led - 38 accounts"
    )
    expect(page.get_by_test_id("ring-card-RING-0041")).to_contain_text(
        "88"
    )
    expect(page.get_by_test_id("ring-card-RING-0041")).to_contain_text(
        "Device"
    )
    expect(
        page.locator('[data-testid="ring-card-RING-0041"] .metric-chip').nth(0)
    ).to_have_attribute(
        "data-tip",
        "Number of accounts assigned to this detected fraud-ring community.",
    )

    page.get_by_test_id("select-all-rings").check()

    expect(page.get_by_test_id("selected-count")).to_have_text("6 selected")
    expect(page.get_by_test_id("load-selected")).to_be_enabled()
    expect(page.get_by_test_id("ring-checkbox-RING-0041")).to_be_checked()

    page.get_by_test_id("select-all-rings").uncheck()

    expect(page.get_by_test_id("selected-count")).to_have_text("0 selected")
    expect(page.get_by_test_id("load-selected")).to_be_disabled()

    page.get_by_test_id("ring-checkbox-RING-0041").check()

    expect(page.get_by_test_id("selected-count")).to_have_text("1 selected")
    expect(page.get_by_test_id("load-selected")).to_be_enabled()
    expect(page.get_by_test_id("select-all-rings")).not_to_be_checked()
    assert page.get_by_test_id("select-all-rings").evaluate(
        "element => element.indeterminate"
    )


def test_back_navigation_preserves_search_selection(
    page: Page, base_url: str
) -> None:
    page.goto(base_url)

    page.get_by_test_id("search-submit").click()
    page.get_by_test_id("ring-checkbox-RING-0041").check()
    page.get_by_test_id("load-selected").click()

    expect(page.get_by_test_id("screen-load")).to_be_visible()

    page.get_by_test_id("back-to-search").click()

    expect(page.get_by_test_id("screen-search")).to_be_visible()
    expect(page.get_by_test_id("results-panel")).to_be_visible()
    expect(page.get_by_test_id("ring-checkbox-RING-0041")).to_be_checked()
    expect(page.get_by_test_id("selected-count")).to_have_text("1 selected")
