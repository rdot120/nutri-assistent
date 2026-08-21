"""
Debug: Click the tooltip-trigger submit button to save.
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
                    return { x: r.x + r.width/2, y: r.y + r.height/2, text: card.textContent.trim() };
                }
            }
            return null;
        }
    """)
    print(f"Card: {first_card['text']}")
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

    # Get the tooltip-trigger submit button and check what it is
    tooltip_info = page.evaluate("""
        () => {
            const form = document.querySelector('#form-nutri-add');
            if (!form) return { error: 'no form' };
            const submitBtn = form.querySelector('button[type="submit"]');
            if (!submitBtn) return { error: 'no submit in form' };
            const r = submitBtn.getBoundingClientRect();
            return {
                text: submitBtn.textContent.trim(),
                slot: submitBtn.getAttribute('data-slot'),
                ariaLabel: submitBtn.getAttribute('aria-label'),
                rect: { x: r.x, y: r.y, w: r.width, h: r.height },
                html: submitBtn.outerHTML.substring(0, 500),
                // Check for tooltip
                tooltipText: submitBtn.closest('[data-slot="tooltip-trigger"]')?.getAttribute('data-slot') || '',
                parentHTML: submitBtn.parentElement?.outerHTML?.substring(0, 500) || ''
            };
        }
    """)
    print(f"\nTooltip-trigger submit button:")
    print(json.dumps(tooltip_info, indent=2, default=str))

    # Also check: is there a floating "Salvar" button somewhere?
    all_salvar = page.evaluate("""
        () => {
            const btns = document.querySelectorAll('button');
            const results = [];
            for (const b of btns) {
                if (b.textContent.trim().includes('Salvar')) {
                    const r = b.getBoundingClientRect();
                    results.push({
                        text: b.textContent.trim(),
                        type: b.type,
                        slot: b.getAttribute('data-slot'),
                        rect: { x: r.x, y: r.y, w: r.width, h: r.height },
                        visible: r.width > 0 && r.height > 0,
                        inDialog: !!b.closest('[data-slot="dialog-content"]'),
                        form: b.form?.id || ''
                    });
                }
            }
            return results;
        }
    """)
    print(f"\nButtons with 'Salvar' text: {len(all_salvar)}")
    for b in all_salvar:
        print(f"  '{b['text']}' type={b['type']} slot={b['slot']} form={b['form']} visible={b['visible']} inDialog={b['inDialog']}")

    # Check: maybe the submit button is hidden and the save happens via the form's onSubmit
    # Let's try pressing Enter to submit
    print("\n=== Trying Enter key to submit ===")
    page.keyboard.press("Enter")
    time.sleep(3)

    # Check if dialog closed
    dialog_still = page.evaluate("""
        () => {
            const d = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
            if (!d) return { closed: true };
            const title = d.querySelector('[data-slot="dialog-title"]')?.textContent || '';
            return { closed: false, title: title };
        }
    """)
    print(f"After Enter: {dialog_still}")

finally:
    session.stop()
