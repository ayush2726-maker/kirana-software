from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "owner-stable.html").read_text(encoding="utf-8")
JS = (ROOT / "static" / "owner-stable.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "owner-stable.css").read_text(encoding="utf-8")


def test_reports_is_present_in_owner_navigation() -> None:
    assert 'id="page-reports"' in HTML
    assert HTML.count('data-page="reports"') >= 3
    assert '<b>Reports</b>' in HTML
    assert 'id="report-from"' in HTML
    assert 'id="report-to"' in HTML
    assert 'id="load-report"' in HTML


def test_reports_runtime_loads_summary_and_renders_all_sections() -> None:
    assert "if (pageName === 'reports')" in JS
    assert "renderReportCatalog();" in JS
    assert "'/api/reports/summary?date_from='" in JS
    assert "'/api/reports/detail?report='" in JS
    assert "function setReportPreset(" in JS
    assert "function renderReports(" in JS
    assert "function renderReportCatalog(" in JS
    assert "function openDetailedReport(" in JS
    assert "function downloadDetailedReport(" in JS
    assert "function downloadProtected(" in JS
    for identifier in (
        "#report-net-sales",
        "#report-net-purchases",
        "#report-margin",
        "#report-stock",
        "#report-top-items",
    ):
        assert identifier in JS


def test_reports_directory_has_requested_business_report_groups() -> None:
    assert 'id="report-directory-view"' in HTML
    assert 'id="report-detail-overlay"' in HTML
    assert 'id="report-search"' in HTML
    for label in (
        "Transaction Reports",
        "Party Reports",
        "GST Reports",
        "Item / Stock Reports",
        "Expense Reports",
        "Loan Reports",
        "Bill Wise Profit & Loss",
        "GSTR-3B Summary",
        "Stock Transfer Report",
    ):
        assert label in JS
    assert ".report-category-card" in CSS
    assert ".report-detail-sheet" in CSS


def test_redesign_keeps_mobile_navigation_and_safe_touch_layout() -> None:
    for page in ("home", "dashboard", "items", "menu"):
        assert f'data-page="{page}"' in HTML
    assert ".bottom-nav" in CSS
    assert "env(safe-area-inset-bottom)" in CSS
    assert "@media (max-width: 700px)" in CSS
    assert "#kirana-smart-fixed { display: none !important; }" in CSS
