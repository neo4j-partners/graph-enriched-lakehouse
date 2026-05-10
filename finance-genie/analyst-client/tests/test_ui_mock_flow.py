from __future__ import annotations

from playwright.sync_api import Page, expect


def test_complete_mock_analyst_workflow(page: Page, base_url: str) -> None:
    page.goto(base_url)

    expect(page.get_by_text("What are you looking for?")).to_be_visible()
    page.get_by_test_id("search-submit").click()

    expect(page.get_by_test_id("results-panel")).to_be_visible()
    expect(page.get_by_test_id("ring-count")).to_have_text("6 rings")
    expect(page.get_by_test_id("ring-row-RING-0041")).to_contain_text("RING-0041")
    expect(page.get_by_test_id("ring-row-RING-0087")).to_contain_text("RING-0087")

    page.get_by_test_id("ring-checkbox-RING-0041").check()
    page.get_by_test_id("ring-checkbox-RING-0087").check()

    expect(page.get_by_test_id("selected-count")).to_have_text("2 selected")
    page.get_by_test_id("load-selected").click()

    expect(page.get_by_test_id("screen-load")).to_be_visible()
    expect(page.get_by_test_id("load-title")).to_have_text(
        "Loading 2 fraud rings into Databricks Lakehouse"
    )
    expect(page.get_by_test_id("load-rings")).to_contain_text("RING-0041")
    expect(page.get_by_test_id("load-rings")).to_contain_text("RING-0087")
    expect(page.get_by_test_id("preview-section")).to_be_visible(timeout=8000)
    expect(page.get_by_test_id("counts-summary")).to_contain_text("60")
    expect(page.get_by_test_id("counts-summary")).to_contain_text("6")
    expect(page.get_by_test_id("counts-summary")).to_contain_text("312")
    expect(page.get_by_test_id("quality-checks")).to_contain_text("Pass")

    page.get_by_test_id("continue-analysis").click()

    expect(page.get_by_test_id("screen-analysis")).to_be_visible()
    expect(page.get_by_test_id("data-tables-list")).to_contain_text(
        "fraud_signals.accounts"
    )
    expect(page.get_by_test_id("data-tables-list")).to_contain_text("60 rows")
    expect(page.get_by_test_id("export-bar")).not_to_be_visible()

    page.get_by_test_id("ask-input").fill(
        "Which accounts have the highest risk scores?"
    )
    page.get_by_test_id("ask-submit").click()

    expect(page.get_by_test_id("chat-history")).to_contain_text(
        "Here are the top 5 accounts by risk score across your loaded rings."
    )
    expect(page.get_by_test_id("chat-history")).to_contain_text("ACC-100291")
    expect(page.get_by_test_id("chat-history")).to_contain_text("RING-0087")
    expect(page.get_by_test_id("export-bar")).to_be_visible()

    page.get_by_test_id("export-report").click()

    expect(page.get_by_test_id("report-modal")).to_be_visible()
    expect(page.get_by_test_id("report-body")).to_contain_text("RING-0041")
    expect(page.get_by_test_id("report-body")).to_contain_text("RING-0087")
    expect(page.get_by_test_id("report-body")).to_contain_text("High risk score")
    expect(page.get_by_test_id("report-body")).to_contain_text("RING-0041-00")
