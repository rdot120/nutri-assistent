"""
Debug: Find the exact save button in the edit dialog.
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

    # Open first card
    first_card = page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
            for (const card of cards) {
                if (card.tagName !== 'DIV') continue;
                const r = card.getBoundingClientRect();
                if (r.width > 0 && r.height > 0 && card.textContent.trim().length > 2) {
                    return { x: r.x + r.width/2, y: r.y + r.height/2 };
                }
            }
            return null;
        }
    """)
    page.mouse.click(first_card['x'], first_card['y'])
    time.sleep(1.5)

    # Click square-pen
    btn = page.evaluate("""
        () => {
            const popover = document.querySelector('[data-slot="popover-content"]');
            const triggers = popover.querySelectorAll('[data-slot="dialog-trigger"]');
            const r = triggers[0].getBoundingClientRect();
            return { x: r.x + r.width/2, y: r.y + r.height/2 };
        }
    """)
    page.mouse.click(btn['x'], btn['y'])
    time.sleep(2)

    # List ALL buttons in the dialog
    dialog_buttons = page.evaluate("""
        () => {
            const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
            if (!dialog) return { error: 'no dialog' };

            const buttons = dialog.querySelectorAll('button');
            return Array.from(buttons).map((b, i) => {
                const r = b.getBoundingClientRect();
                return {
                    index: i,
                    text: b.textContent.trim().substring(0, 40),
                    type: b.type,
                    dataSlot: b.getAttribute('data-slot') || '',
                    ariaLabel: b.getAttribute('aria-label') || '',
                    visible: r.width > 0 && r.height > 0,
                    rect: { x: r.x, y: r.y, w: r.width, h: r.height },
                    className: b.className.substring(0, 100),
                    parentSlot: b.parentElement?.getAttribute('data-slot') || ''
                };
            });
        }
    """)
    print(f"Dialog buttons ({len(dialog_buttons)}):")
    for b in dialog_buttons:
        vis = "VIS" if b['visible'] else "---"
        print(f"  [{vis}] #{b['index']} text='{b['text']}' type={b['type']} slot={b['dataSlot']} parent={b['parentSlot']} class={b['className'][:60]}")

    # Specifically look for submit buttons
    submit_buttons = [b for b in dialog_buttons if b['type'] == 'submit' and b['visible']]
    print(f"\nVisible submit buttons: {len(submit_buttons)}")
    for b in submit_buttons:
        print(f"  #{b['index']} text='{b['text']}' slot={b['dataSlot']} rect={b['rect']}")

finally:
    session.stop()
