"""
Debug: Click square-pen icon, wait for form to load, inspect thoroughly.
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

    # Step 1: Click first card
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
    time.sleep(2)

    # Step 2: Find and click the first dialog-trigger (square-pen)
    btn = page.evaluate("""
        () => {
            const popover = document.querySelector('[data-slot="popover-content"]');
            if (!popover) return null;
            const triggers = popover.querySelectorAll('[data-slot="dialog-trigger"]');
            if (triggers.length === 0) return null;
            const t = triggers[0];
            const r = t.getBoundingClientRect();
            return { x: r.x + r.width/2, y: r.y + r.height/2, svg: t.querySelector('svg')?.getAttribute('class') };
        }
    """)
    print(f"\nClicking square-pen at ({btn['x']}, {btn['y']})")
    page.mouse.click(btn['x'], btn['y'])

    # Wait for form to load - check every 500ms for up to 10 seconds
    print("\nWaiting for dialog/sheet to load...")
    for i in range(20):
        time.sleep(0.5)
        state = page.evaluate("""
            () => {
                // Check ALL elements with role="dialog"
                const dialogs = document.querySelectorAll('[role="dialog"]');
                const openDialogs = [];
                for (const d of dialogs) {
                    const r = d.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        const inputs = d.querySelectorAll('input');
                        const textareas = d.querySelectorAll('textarea');
                        const selects = d.querySelectorAll('select');
                        const comboboxes = d.querySelectorAll('[role="combobox"]');
                        openDialogs.push({
                            slot: d.getAttribute('data-slot'),
                            id: d.id,
                            ariaLabel: d.getAttribute('aria-label'),
                            inputCount: inputs.length,
                            textareaCount: textareas.length,
                            selectCount: selects.length,
                            comboboxCount: comboboxes.length,
                            textLen: d.textContent.length,
                            textPreview: d.textContent.substring(0, 100)
                        });
                    }
                }

                // Also check sheet-content specifically
                const sheets = document.querySelectorAll('[data-slot="sheet-content"]');
                const openSheets = [];
                for (const s of sheets) {
                    const r = s.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        openSheets.push({
                            slot: 'sheet-content',
                            inputCount: s.querySelectorAll('input').length,
                            textLen: s.textContent.length,
                            textPreview: s.textContent.substring(0, 100)
                        });
                    }
                }

                return { openDialogs, openSheets };
            }
        """)
        if any(d['inputCount'] > 0 or d['selectCount'] > 0 or d['textareaCount'] > 0
               for d in state['openDialogs']):
            print(f"\n  [{i*500}ms] FORM FOUND!")
            print(json.dumps(state, indent=2))
            break
        if i % 4 == 0:
            total_inputs = sum(d['inputCount'] for d in state['openDialogs'])
            print(f"  [{i*500}ms] dialogs={len(state['openDialogs'])} sheets={len(state['openSheets'])} total_inputs={total_inputs}")

    # Final deep inspection of all open elements
    print("\n=== FINAL STATE ===")
    final = page.evaluate("""
        () => {
            const all = document.querySelectorAll('[role="dialog"], [data-slot="sheet-content"]');
            const results = [];
            for (const el of all) {
                const r = el.getBoundingClientRect();
                if (r.width === 0 || r.height === 0) continue;
                results.push({
                    tag: el.tagName,
                    slot: el.getAttribute('data-slot'),
                    role: el.getAttribute('role'),
                    id: el.id,
                    outerHTML: el.outerHTML.substring(0, 3000),
                    inputCount: el.querySelectorAll('input').length,
                    inputs: Array.from(el.querySelectorAll('input')).map(i => ({
                        id: i.id, name: i.name, placeholder: i.placeholder, type: i.type
                    })),
                    textareaCount: el.querySelectorAll('textarea').length,
                    selectCount: el.querySelectorAll('select').length,
                    comboboxCount: el.querySelectorAll('[role="combobox"]').length,
                    labelCount: el.querySelectorAll('label').length,
                    labels: Array.from(el.querySelectorAll('label')).map(l => l.textContent.trim().substring(0, 40))
                });
            }
            return results;
        }
    """)
    for item in final:
        print(f"\n{item['slot'] or item['role']} ({item['inputCount']} inputs, {item['textareaCount']} textareas, {item['selectCount']} selects):")
        print(f"  HTML preview: {item['outerHTML'][:1000]}")
        if item['inputs']:
            for inp in item['inputs']:
                print(f"  Input: id={inp['id']} name={inp['name']} placeholder={inp['placeholder']} type={inp['type']}")
        if item['labels']:
            print(f"  Labels: {item['labels'][:10]}")

    page.screenshot(path="nutri_auto/debug_final_screenshot.png", full_page=False)
    print("\nScreenshot saved")

finally:
    session.stop()
