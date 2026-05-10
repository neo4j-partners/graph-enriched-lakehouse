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

    page.get_by_test_id("ring-checkbox-RING-0041").check()

    expect(page.get_by_test_id("selected-count")).to_have_text("1 selected")
    expect(page.get_by_test_id("load-selected")).to_be_enabled()


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
