"""Capture the real, offline Streamlit demo without changing application files.

uv run --no-project --with playwright python presentation/capture_demo.py
Requires the app on localhost:8503 and an installed Chrome or Edge browser.
"""

from pathlib import Path
import re

from playwright.sync_api import sync_playwright


HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
ASSETS.mkdir(exist_ok=True)


def main():
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    executable = next((p for p in candidates if p.exists()), None)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            **({"executable_path": str(executable)} if executable else {}),
        )
        page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1.5)
        page.set_default_timeout(30000)
        page.goto("http://localhost:8503")
        page.get_by_role("button", name="Deliver Priya's email", exact=True).wait_for()
        page.add_style_tag(content="[data-testid=stSidebar]{display:none!important;} [data-testid=stToast]{display:none!important;} .block-container{max-width:1480px!important;}")
        page.screenshot(path=ASSETS / "demo-ready.png")
        page.get_by_role("button", name="Deliver Priya's email", exact=True).click()
        page.get_by_role("button", name="Run the agents", exact=True).click()
        approve = page.get_by_role("button", name="Approve as organiser (Kavya)", exact=True)
        approve.wait_for()
        graph = page.locator('[data-testid="stExpander"]').filter(has_text="Impact map: everything this one email touches")
        graph.screenshot(path=ASSETS / "impact-map.png")
        page.get_by_text(re.compile(r"Step 3\. The plan has")).scroll_into_view_if_needed()
        page.screenshot(path=ASSETS / "approval-plan.png")
        approve.click()
        page.get_by_role("button", name="Execute approved plan", exact=True).click()
        delta = page.get_by_role("button", name=re.compile(r"Approve \d+ changed actions"))
        delta.wait_for()
        assert "6 changed actions" in delta.inner_text()
        page.get_by_text(re.compile(r"Step 5\. Someone changed")).scroll_into_view_if_needed()
        page.screenshot(path=ASSETS / "delta-approval.png")
        page.get_by_text(re.compile(r"Only the 6 new or changed steps")).scroll_into_view_if_needed()
        page.screenshot(path=ASSETS / "delta-table.png")
        page.get_by_text("Failure and recovery — what actually happened").scroll_into_view_if_needed()
        page.screenshot(path=ASSETS / "failure-recovery.png")
        delta.click()
        page.get_by_role("button", name="Execute approved plan", exact=True).click()
        page.get_by_role("button", name="Verify the results", exact=True).click()
        page.get_by_role("button", name="Replay the email 10 times", exact=True).click()
        page.get_by_text(re.compile(r"\d+ records changed again")).wait_for()
        checked = page.get_by_role("heading", name="Checked: 21 passed, 0 failed", exact=True)
        checked.wait_for()
        checked.scroll_into_view_if_needed()
        page.screenshot(path=ASSETS / "verified-replay.png")
        assert "0 records changed again" in page.inner_text('[data-testid="stMain"]')
        page.locator('[data-testid="stMain"]').evaluate("e => e.scrollTop = 0")
        page.screenshot(path=ASSETS / "demo-verified.png")
        browser.close()
    print("Captured real application screenshots; 21 checks passed; replay changed 0 records.")


if __name__ == "__main__":
    main()
