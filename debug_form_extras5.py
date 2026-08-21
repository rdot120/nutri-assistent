"""
Click 'Clique aqui' (dialog-trigger) to open the extra fields dialog.
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

    # Open edit dialog
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
    page.mouse.click(first_card['x'], first_card['y'])
    time.sleep(2)

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

    # Click "Campos Extras" tab
    extras_tab = page.evaluate("""
        () => {
            const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
            const tabs = dialog.querySelectorAll('[data-slot="tabs-trigger"]');
            for (const tab of tabs) {
                if (tab.textContent.includes('Extras')) {
                    const r = tab.getBoundingClientRect();
                    return { x: r.x + r.width/2, y: r.y + r.height/2 };
                }
            }
            return null;
        }
    """)
    page.mouse.click(extras_tab['x'], extras_tab['y'])
    time.sleep(1)

    # Click "Clique aqui" which opens ANOTHER dialog
    clique_aqui = page.evaluate("""
        () => {
            const dialogs = document.querySelectorAll('[data-slot="dialog-content"][data-state="open"]');
            for (const dialog of dialogs) {
                const btns = dialog.querySelectorAll('button[data-slot="dialog-trigger"]');
                for (const b of btns) {
                    if (b.textContent.trim() === 'Clique aqui') {
                        const r = b.getBoundingClientRect();
                        return { x: r.x + r.width/2, y: r.y + r.height/2 };
                    }
                }
            }
            return null;
        }
    """)
    if clique_aqui:
        page.mouse.click(clique_aqui['x'], clique_aqui['y'])
        time.sleep(3)

        # Check what opened
        all_dialogs = page.evaluate("""
            () => {
                const dialogs = document.querySelectorAll('[role="dialog"]');
                const results = [];
                for (const d of dialogs) {
                    const r = d.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        const inputs = d.querySelectorAll('input, select, textarea');
                        const labels = d.querySelectorAll('label');
                        results.push({
                            slot: d.getAttribute('data-slot'),
                            id: d.id,
                            inputCount: inputs.length,
                            labelCount: labels.length,
                            textPreview: d.textContent.substring(0, 200),
                            inputs: Array.from(inputs).map(i => ({
                                name: i.name, type: i.type || i.tagName.toLowerCase(),
                                value: (i.value || '').substring(0, 30), placeholder: i.placeholder || ''
                            })),
                            labels: Array.from(labels).map(l => l.textContent.trim().substring(0, 40))
                        });
                    }
                }
                return results;
            }
        """)
        print("=== Open dialogs after clicking Clique aqui ===")
        for d in all_dialogs:
            print(f"\n{d['slot']} ({d['inputCount']} inputs, {d['labelCount']} labels):")
            print(f"  text: {d['textPreview'][:200]}")
            if d['inputs']:
                for inp in d['inputs']:
                    print(f"  input: {inp['name']} ({inp['type']}) = '{inp['value']}' placeholder='{inp['placeholder']}'")
            if d['labels']:
                print(f"  labels: {d['labels'][:10]}")

    page.screenshot(path="nutri_auto/debug_extras_dialog.png", full_page=False)

finally:
    session.stop()
