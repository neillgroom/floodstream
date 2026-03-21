"""
Venue portal explorer — keeps browser open, takes screenshots on demand.
Usage: python venue_explore.py
  Then press Enter to take a screenshot, or type 'quit' to exit.
"""

from playwright.sync_api import sync_playwright
import os

SCREENSHOT_DIR = r"C:\tmp\venue_live"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.goto("https://fountain.venueclaims.com")

        print("\nBrowser open at fountain.venueclaims.com")
        print("Navigate freely, then come back here and press Enter to screenshot.")
        print("Type 'quit' to close.\n")

        count = 0
        while True:
            try:
                cmd = input(f"[{count}] Press Enter to screenshot (or 'quit'): ").strip()
            except EOFError:
                # Non-interactive — just wait
                page.wait_for_timeout(3600000)
                break

            if cmd.lower() == "quit":
                break

            path = os.path.join(SCREENSHOT_DIR, f"venue_{count:03d}.png")
            page.screenshot(path=path, full_page=False)
            print(f"  Saved: {path}")
            count += 1

        browser.close()


if __name__ == "__main__":
    main()
