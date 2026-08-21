"""
Debug: Check actual form structure in dialog for save mechanism.
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

    # Get full dialog HTML structure (focusing on buttons/forms at end)
    dialog_html = page.evaluate("""
        () => {
            const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
            if (!dialog) return { error: 'no dialog' };

            // Get the last 2000 chars of HTML (where the save button should be)
            const fullHTML = dialog.outerHTML;
            return {
                length: fullHTML.length,
                last2000: fullHTML.substring(fullHTML.length - 2000),
                forms: Array.from(dialog.querySelectorAll('form')).map(f => ({
                    action: f.action,
                    method: f.method,
                    html: f.outerHTML.substring(0, 500)
                })),
                // Find the submit button that is inside the dialog-close area
                closeAreaHTML: (() => {
                    const closeBtn = dialog.querySelector('[data-slot="dialog-close"]');
                    return closeBtn ? closeBtn.outerHTML.substring(0, 1000) : 'none';
                })()
            };
        }
    """)
    print("Forms in dialog:", json.dumps(dialog_html.get('forms', []), indent=2))
    print("\nClose area HTML:")
    print(dialog_html.get('closeAreaHTML', 'none'))
    print("\nLast 2000 chars of dialog HTML:")
    print(dialog_html.get('last2000', '')[:2000])

finally:
    session.stop()
