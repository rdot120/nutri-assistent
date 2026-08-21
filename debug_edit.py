"""
Debug: Click the edit icon in the popover to open the Sheet form.
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
    session.page.goto(settings.platform.nutri_url, wait_until="networkidle", timeout=30000)
    time.sleep(3)
    page = session.page

    # Step 1: Click the first food card to open popover
    first_card = page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
            for (const card of cards) {
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

    # Step 2: Find the dialog-trigger buttons in the popover
    dialog_triggers = page.evaluate("""
        () => {
            const popover = document.querySelector('[data-slot="popover-content"]');
            if (!popover) return { error: 'no popover' };

            const triggers = popover.querySelectorAll('[data-slot="dialog-trigger"]');
            return {
                count: triggers.length,
                items: Array.from(triggers).map((t, i) => {
                    const r = t.getBoundingClientRect();
                    const svg = t.querySelector('svg');
                    const svgClass = svg ? svg.getAttribute('class') : '';
                    return {
                        index: i,
                        type: t.type,
                        ariaHaspopup: t.getAttribute('aria-haspopup'),
                        ariaControls: t.getAttribute('aria-controls'),
                        dataState: t.getAttribute('data-state'),
                        svgClass: svgClass,
                        visible: r.width > 0 && r.height > 0,
                        rect: { x: r.x + r.width/2, y: r.y + r.height/2, w: r.width, h: r.height }
                    };
                })
            };
        }
    """)
    print(f"\nDialog triggers in popover: {json.dumps(dialog_triggers, indent=2)}")

    # Step 3: Click the FIRST dialog-trigger (edit icon - square-pen)
    if dialog_triggers.get('items'):
        edit_trigger = dialog_triggers['items'][0]  # First one is the edit
        print(f"\nClicking edit dialog-trigger at ({edit_trigger['rect']['x']}, {edit_trigger['rect']['y']})")
        print(f"  SVG class: {edit_trigger['svgClass']}")

        page.mouse.click(edit_trigger['rect']['x'], edit_trigger['rect']['y'])
        time.sleep(3)

        # Step 4: Check what opened
        # Could be a Sheet or a Dialog
        sheet = page.evaluate("""
            () => {
                // Check for Sheet
                let el = document.querySelector('[data-slot="sheet-content"]');
                if (el) {
                    const inputs = Array.from(el.querySelectorAll('input'));
                    const selects = Array.from(el.querySelectorAll('select, [role="combobox"], [role="listbox"]'));
                    const textareas = Array.from(el.querySelectorAll('textarea'));
                    const labels = Array.from(el.querySelectorAll('label'));
                    return {
                        type: 'sheet',
                        found: true,
                        textPreview: el.textContent.substring(0, 200),
                        inputCount: inputs.length,
                        inputs: inputs.map(i => ({
                            id: i.id, name: i.name, placeholder: i.placeholder,
                            type: i.type, value: i.value,
                            label: i.getAttribute('aria-label') || ''
                        })),
                        selectCount: selects.length,
                        selects: selects.map(s => ({
                            id: s.id, name: s.name, role: s.getAttribute('role'),
                            text: s.textContent.substring(0, 50)
                        })),
                        textareaCount: textareas.length,
                        textareas: textareas.map(t => ({
                            id: t.id, name: t.name, placeholder: t.placeholder
                        })),
                        labels: labels.map(l => l.textContent.trim().substring(0, 50)),
                        buttons: Array.from(el.querySelectorAll('button')).map(b => ({
                            text: b.textContent.trim().substring(0, 30),
                            type: b.type
                        }))
                    };
                }

                // Check for Dialog
                el = document.querySelector('[role="dialog"]');
                if (el) {
                    return {
                        type: 'dialog',
                        found: true,
                        textPreview: el.textContent.substring(0, 200),
                        inputCount: el.querySelectorAll('input').length
                    };
                }

                // Check for any overlay/modal
                const overlays = document.querySelectorAll('[data-slot="dialog-content"], [data-state="open"]');
                return {
                    type: 'unknown',
                    found: false,
                    overlayCount: overlays.length,
                    allOpen: Array.from(overlays).map(o => ({
                        slot: o.getAttribute('data-slot'),
                        state: o.getAttribute('data-state'),
                        text: o.textContent.substring(0, 100)
                    }))
                };
            }
        """)
        print(f"\nOpened element: {json.dumps(sheet, indent=2)}")

        # Screenshot
        page.screenshot(path="nutri_auto/debug_edit_screenshot.png", full_page=False)
        print("\nScreenshot saved: debug_edit_screenshot.png")

finally:
    session.stop()
