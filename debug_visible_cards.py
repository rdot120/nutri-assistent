"""
Debug: What visible cards exist after search?
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

    # Search
    search = page.query_selector('input[placeholder*="Procure"]')
    search.fill("ARROZ BRANCO KG")
    time.sleep(2)

    # Check visible cards
    cards = page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
            const results = [];
            for (const card of cards) {
                const r = card.getBoundingClientRect();
                if (r.width > 0 && r.height > 0 && r.x >= 0 && r.x < window.innerWidth) {
                    results.push({
                        text: card.textContent.trim(),
                        x: r.x, y: r.y, w: r.width, h: r.height,
                        parent: card.parentElement?.getAttribute('data-slot') || '',
                        grandparent: card.parentElement?.parentElement?.className?.substring(0, 80) || ''
                    });
                }
            }
            return { total: cards.length, visible: results.length, items: results.slice(0, 10) };
        }
    """)
    print(f"Total cards: {cards['total']}, visible+in-viewport: {cards['visible']}")
    for c in cards['items']:
        print(f"  text='{c['text']}' pos=({c['x']},{c['y']}) size={c['w']}x{c['h']} parent={c['parent']}")

    # Also check: are there card-content elements with food names?
    card_contents = page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-slot="card-content"]');
            const results = [];
            for (const card of cards) {
                const r = card.getBoundingClientRect();
                if (r.width > 0 && r.height > 0 && r.x >= 0 && r.x < window.innerWidth) {
                    results.push({
                        text: card.textContent.trim().substring(0, 80),
                        x: r.x, y: r.y
                    });
                }
            }
            return results.slice(0, 10);
        }
    """)
    print(f"\nCard contents visible: {len(card_contents)}")
    for c in card_contents:
        print(f"  text='{c['text']}' pos=({c['x']},{c['y']})")

finally:
    session.stop()
