"""
Debug: Inspect actual DOM structure after search.
"""
import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from browser.session import SessionManager

settings = Settings.load()
settings.load_env()

session = SessionManager(
    user_data_dir=settings.platform.user_data_dir,
    headless=True,
    timeout=30000,
)

try:
    session.start()
    session.login(settings.platform.login_url, settings.platform.username, settings.platform.password)
    page = session.page
    page.goto(settings.platform.nutri_url, wait_until="networkidle", timeout=30000)
    time.sleep(3)

    # Before search: check first few cards
    before = page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
            return Array.from(cards).slice(0, 3).map(c => ({
                text: c.textContent.trim(),
                html: c.outerHTML.substring(0, 500),
                rect: c.getBoundingClientRect()
            }));
        }
    """)
    print("=== BEFORE SEARCH ===")
    for c in before:
        print(f"  text='{c['text']}' pos=({c['rect']['x']},{c['rect']['y']})")
        print(f"  html: {c['html'][:300]}")
        print()

    # Search
    search = page.query_selector('input[placeholder*="Procure"]')
    search.fill("ARROZ BRANCO KG")
    time.sleep(2)

    # After search
    after = page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
            return Array.from(cards).map(c => ({
                text: c.textContent.trim(),
                html: c.outerHTML.substring(0, 800),
                rect: c.getBoundingClientRect()
            }));
        }
    """)
    print(f"\n=== AFTER SEARCH: {len(after)} popover-triggers ===")
    for c in after:
        print(f"  text='{c['text']}' pos=({c['rect']['x']},{c['rect']['y']}) size={c['rect']['width']}x{c['rect']['height']}")
        print(f"  html: {c['html'][:500]}")
        print()

    # Also check: what does the page actually show?
    all_text = page.evaluate("""
        () => {
            const main = document.querySelector('main') || document.body;
            return main.textContent.substring(0, 1000);
        }
    """)
    print(f"\n=== PAGE TEXT (first 1000 chars) ===")
    print(all_text[:1000])

finally:
    session.stop()
