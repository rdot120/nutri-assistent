"""
Debug: Find all submit buttons on page, check form submission mechanism.
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

    # Open edit dialog
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

    # Check the form submission
    form_info = page.evaluate("""
        () => {
            const form = document.querySelector('#form-nutri-add');
            if (!form) return { error: 'no form' };

            // Check form attributes
            const info = {
                id: form.id,
                action: form.action,
                method: form.method,
                childCount: form.children.length,
            };

            // Look for submit buttons ANYWHERE that might be associated
            const allSubmitBtns = document.querySelectorAll('button[type="submit"]');
            info.allSubmitBtns = Array.from(allSubmitBtns).map(b => {
                const r = b.getBoundingClientRect();
                return {
                    text: b.textContent.trim().substring(0, 30),
                    slot: b.getAttribute('data-slot') || '',
                    form: b.form?.id || '',
                    rect: { x: r.x, y: r.y, w: r.width, h: r.height },
                    visible: r.width > 0 && r.height > 0,
                    inDialog: !!b.closest('[data-slot="dialog-content"]')
                };
            });

            // Check if form has an onsubmit handler
            info.onsubmit = form.onsubmit ? form.onsubmit.toString().substring(0, 200) : null;

            // Check for buttons inside the form
            const formButtons = form.querySelectorAll('button');
            info.formButtons = Array.from(formButtons).map(b => ({
                text: b.textContent.trim().substring(0, 30),
                type: b.type,
                slot: b.getAttribute('data-slot') || ''
            }));

            return info;
        }
    """)
    print("Form info:")
    print(json.dumps(form_info, indent=2, default=str))

    # Try: click the form's submit button (#7 from earlier, which is inside dialog-close)
    # But maybe we need to scroll down to see it?
    print("\n=== Trying to scroll dialog to find save button ===")
    save_pos = page.evaluate("""
        () => {
            const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
            if (!dialog) return null;

            // Find ALL buttons and their positions relative to dialog
            const dialogRect = dialog.getBoundingClientRect();
            const buttons = dialog.querySelectorAll('button');
            const results = [];
            for (const b of buttons) {
                const r = b.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) {
                    results.push({
                        text: b.textContent.trim().substring(0, 30),
                        type: b.type,
                        slot: b.getAttribute('data-slot') || '',
                        rect: { x: r.x, y: r.y, w: r.width, h: r.height },
                        inDialogRect: r.x >= dialogRect.x && r.y >= dialogRect.y &&
                                      r.right <= dialogRect.right && r.bottom <= dialogRect.bottom
                    });
                }
            }
            return { dialogRect: dialogRect, buttons: results };
        }
    """)
    if save_pos:
        print(f"Dialog rect: {save_pos['dialogRect']}")
        for b in save_pos['buttons']:
            inDialog = "IN-DLG" if b['inDialogRect'] else "OUTSIDE"
            print(f"  [{inDialog}] type={b['type']} slot={b['slot']} text='{b['text']}' rect={b['rect']}")

finally:
    session.stop()
