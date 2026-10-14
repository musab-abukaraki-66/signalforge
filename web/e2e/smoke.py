"""Browser smoke test for the public app (Playwright for Python).

Usage: python e2e/smoke.py BASE_URL [SCREENSHOT_DIR]
Checks desktop (1440) and mobile (390): routes, demo filters, decision room arithmetic,
CSV upload journeys (valid, malformed, empty, oversized, duplicates/missing), exports and
that no console errors or horizontal overflow occur.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = sys.argv[2] if len(sys.argv) > 2 else None
EXE = os.environ.get("CHROMIUM_PATH") or None
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))


def shot(page, name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        page.screenshot(path=os.path.join(SHOTS, name), full_page=False)


def write(tmp, name, content):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def no_overflow(page):
    return not page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")


def run(browser, label, viewport):
    ctx = browser.new_context(viewport=viewport, accept_downloads=True)
    page = ctx.new_page()
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    tmp = tempfile.mkdtemp()

    # landing
    page.goto(BASE + "/")
    check(
        f"{label}: landing headline",
        page.get_by_role("heading", level=1).inner_text().startswith("Turn raw business data"),
    )
    check(
        f"{label}: landing shows synthetic label",
        page.get_by_text("Synthetic demo", exact=False).first.is_visible(),
    )
    check(f"{label}: landing no horizontal overflow", no_overflow(page))
    shot(page, f"{label}-landing.png")
    page.get_by_role("link", name="Explore the live demo").first.click()
    page.wait_for_url("**/demo")

    # demo
    expect(page.get_by_text("Synthetic demo data — not real business findings")).to_be_visible()
    expect(page.get_by_text("Orders", exact=True).first).to_be_visible()

    def kpi():
        return page.locator(".kpi .v").first.inner_text()

    before = kpi()
    page.get_by_label("Customer state").select_option("SP")
    after = kpi()
    check(f"{label}: state filter changes KPIs", before != after, f"{before} -> {after}")
    page.get_by_label("Customer state").select_option("")
    page.get_by_label("From", exact=True).fill("2018-06-01")
    page.get_by_label("To", exact=True).fill("2018-05-01")
    check(
        f"{label}: empty filter state is explained",
        page.get_by_text("No orders match these filters").is_visible(),
    )
    page.get_by_role("button", name="Reset").click()
    check(f"{label}: reset restores KPIs", kpi() == before)
    check(f"{label}: demo no horizontal overflow", no_overflow(page))
    shot(page, f"{label}-demo-overview.png")
    for tab in (
        "Explorer",
        "Data quality",
        "Trends & forecast",
        "Decision room",
        "Definitions & methods",
    ):
        page.get_by_role("tab", name=tab).click()
        check(
            f"{label}: tab {tab} renders",
            page.get_by_role("tabpanel").is_visible() and no_overflow(page),
        )
        if tab == "Trends & forecast":
            shot(page, f"{label}-demo-forecast.png")
            page.get_by_role("radio", name="Weekly GMV").click()
            check(
                f"{label}: forecast series toggle",
                page.get_by_text("Forecast: next 8 weeks").is_visible(),
            )
        if tab == "Decision room":
            check(
                f"{label}: unknown inputs compute nothing",
                page.get_by_text("Not computed — missing").is_visible(),
            )
            page.get_by_placeholder("unknown").nth(0).fill("0.5")
            page.get_by_placeholder("unknown").nth(1).fill("2")
            page.get_by_placeholder("unknown").nth(2).fill("10")
            check(
                f"{label}: scenario result appears",
                page.get_by_text("Net value under your inputs").is_visible(),
            )
            page.get_by_placeholder("unknown").nth(0).fill("3")
            check(
                f"{label}: invalid rate rejected",
                page.get_by_text("Rescue rate must be a number between 0 and 1").is_visible(),
            )
            shot(page, f"{label}-demo-decision.png")
        if tab == "Data quality":
            shot(page, f"{label}-demo-quality.png")

    # analyzer
    page.goto(BASE + "/analyze")
    expect(page.get_by_text("Private by design")).to_be_visible()
    lines = ["date,region,amount,note"] + [
        f"2023-{(i % 12) + 1:02d}-{(i % 27) + 1:02d},{['N', 'S', 'E'][i % 3]},{10 + i % 50},private-text-{i}"
        for i in range(300)
    ]
    lines += [lines[5], lines[5], "2023-03-03,N,,missing amount"]
    good = write(tmp, "good.csv", "\n".join(lines) + "\n")
    page.set_input_files("#csv-file", good)
    expect(page.get_by_text("1. Data quality")).to_be_visible()
    check(
        f"{label}: duplicates flagged",
        page.get_by_text("exactly repeat an earlier row").is_visible(),
    )
    check(
        f"{label}: missing flagged or counted",
        page.get_by_text("Rows excluded", exact=True).is_visible(),
    )
    check(f"{label}: analysis charts render", page.locator("figure.chart svg").count() >= 2)
    check(f"{label}: analyzer no horizontal overflow", no_overflow(page))
    shot(page, f"{label}-analyze-results.png")
    page.get_by_label("Type of amount").select_option("category")
    check(
        f"{label}: type override recalculates",
        page.get_by_label("Type of amount").input_value() == "category",
    )
    page.get_by_label("Type of amount").select_option("number")
    page.get_by_label("Remove 2 exact duplicate row(s)").check()
    check(
        f"{label}: cleaning preview reports counts",
        page.get_by_text("This export would keep").is_visible(),
    )
    with page.expect_download() as d:
        page.get_by_role("button", name="Download report (JSON)").click()
    report = Path(d.value.path()).read_text(encoding="utf-8")
    data = json.loads(report)
    check(
        f"{label}: report is valid JSON with stats",
        data["rows"] == 303 and "private-text-7" not in report,
        report[:80],
    )
    with page.expect_download() as d2:
        page.get_by_role("button", name="Download cleaned CSV").click()
    cleaned = Path(d2.value.path()).read_text(encoding="utf-8").splitlines()
    check(
        f"{label}: cleaned CSV removed exactly the duplicates",
        len(cleaned) == 1 + 301,
        str(len(cleaned)),
    )
    page.get_by_role("button", name="Remove file / start over").click()
    check(f"{label}: reset returns to upload", page.get_by_text("Drag a CSV here").is_visible())
    check(
        f"{label}: nothing in localStorage",
        page.evaluate("localStorage.length === 0 && sessionStorage.length === 0"),
    )

    for name, content, expected in (
        ("empty.csv", "", "empty"),
        ("malformed.csv", 'a,b\n"unclosed,1\n2,3\n', "never closed"),
        ("header-only.csv", "a,b\n", "no data rows"),
    ):
        path = write(tmp, name, content)
        page.set_input_files("#csv-file", path)
        try:
            expect(page.get_by_role("alert").filter(has_text=expected)).to_be_visible(timeout=5000)
            ok = True
        except AssertionError:
            ok = False
        check(f"{label}: {name} gives a clear error", ok)
    big = write(tmp, "big.csv", "a,b\n" + "1,2\n" * 3_000_000)  # about 12 MB
    page.set_input_files("#csv-file", big)
    try:
        expect(page.get_by_role("alert").filter(has_text="maximum is 10 MB")).to_be_visible(
            timeout=5000
        )
        ok = True
    except AssertionError:
        ok = False
    check(f"{label}: oversized file rejected", ok)
    page.get_by_role("button", name="Try an invented sample").click()
    expect(page.get_by_text("1. Data quality")).to_be_visible()
    check(
        f"{label}: sample loads and shows baseline or reason",
        page.get_by_text("Baseline check").count() + page.get_by_text("complete periods").count()
        >= 1,
    )
    short = write(tmp, "short.csv", "date,amount\n2024-01-01,5\n2024-01-02,6\n2024-01-03,7\n")
    page.get_by_role("button", name="Remove file / start over").click()
    page.set_input_files("#csv-file", short)
    try:
        expect(page.get_by_text("at least 20 are needed")).to_be_visible(timeout=5000)
        ok = True
    except AssertionError:
        ok = False
    check(f"{label}: short series declines to forecast", ok)

    # other pages
    page.goto(BASE + "/methods")
    check(
        f"{label}: methods page",
        page.get_by_role("heading", level=1).inner_text().startswith("Methods"),
    )
    check(f"{label}: no console errors", not errors, "; ".join(errors[:3]))
    resp = page.goto(BASE + "/no-such-page")  # deliberate 404: its own resource error is expected
    check(
        f"{label}: 404 page", resp.status == 404 and page.get_by_text("Page not found").is_visible()
    )
    ctx.close()


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=EXE, args=["--no-sandbox"])
    run(browser, "desktop", {"width": 1440, "height": 900})
    run(browser, "mobile", {"width": 390, "height": 844})
    browser.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
