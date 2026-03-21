"""Launch Venue portal browser and keep it open. Auto-screenshots every 15 seconds."""

from playwright.sync_api import sync_playwright
import os
import time

SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "venue_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto("https://fountain.venueclaims.com")
    print("Browser open. Taking screenshots every 15s.")

    for i in range(240):
        time.sleep(15)
        try:
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, f"shot_{i:03d}.png"))
            print(f"Screenshot {i}")
        except Exception as e:
            print(f"Screenshot {i} failed: {e}")
            break

    browser.close()
