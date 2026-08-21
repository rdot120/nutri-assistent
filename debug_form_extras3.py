"""
Click 'Clique aqui' to load Campos Extras, then capture all fields.
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

    # Click "Clique aqui" link/button
    clique_aqui = page.evaluate("""
        () => {
            const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
            const links = dialog.querySelectorAll('a, button, span');
            for (const el of links) {
                if (el.textContent.trim() === 'Clique aqui') {
                    const r = el.getBoundingClientRect();
                    return { x: r.x + r.width/2, y: r.y + r.height/2, tag: el.tagName };
                }
            }
            return null;
        }
    """)
    print(f"'Clique aqui' element: {clique_aqui}")

    if clique_aqui:
        page.mouse.click(clique_aqui['x'], clique_aqui['y'])
        time.sleep(3)

        # Now capture ALL extras fields
        extras = page.evaluate("""
            () => {
                const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
                const tabsContents = dialog.querySelectorAll('[data-slot="tabs-content"]');
                let activeContent = null;
                for (const tc of tabsContents) {
                    if (tc.getBoundingClientRect().height > 0) {
                        activeContent = tc;
                        break;
                    }
                }
                if (!activeContent) return { error: 'No active content' };

                const fields = [];
                const labels = activeContent.querySelectorAll('label');
                for (const label of labels) {
                    const text = label.textContent.trim();
                    let input = null;
                    if (label.htmlFor) {
                        input = activeContent.querySelector('#' + CSS.escape(label.htmlFor));
                    }
                    if (!input) {
                        let sib = label.nextElementSibling;
                        for (let i = 0; i < 5 && sib; i++) {
                            if (sib.tagName === 'INPUT' || sib.tagName === 'SELECT' || sib.tagName === 'TEXTAREA') {
                                input = sib;
                                break;
                            }
                            const inner = sib.querySelector('input, select, textarea');
                            if (inner) { input = inner; break; }
                            sib = sib.nextElementSibling;
                        }
                    }
                    if (input) {
                        const field = {
                            labelText: text,
                            inputName: input.name || '',
                            inputType: input.type || input.tagName.toLowerCase(),
                            value: input.value || '',
                            placeholder: input.placeholder || ''
                        };
                        if (input.tagName === 'SELECT') {
                            field.options = Array.from(input.querySelectorAll('option')).map(o => ({
                                value: o.value, text: o.textContent.trim(), selected: o.selected
                            }));
                        }
                        fields.push(field);
                    } else {
                        fields.push({ labelText: text, noInput: true });
                    }
                }
                return { fieldCount: fields.length, fields, text: activeContent.textContent.substring(0, 2000) };
            }
        """)
        print(f"\n=== CAMPOS EXTRAS (after Clique aqui) ===")
        print(f"Fields: {extras['fieldCount']}")
        for f in extras['fields']:
            if f.get('noInput'):
                print(f"  [{f['labelText']}] => NO INPUT")
            else:
                extra = ''
                if f.get('options'):
                    extra = f" options={[o['text'] + '(' + o['value'] + ')' for o in f['options'][:5]]}"
                print(f"  [{f['labelText']}] => name={f['inputName']} type={f['inputType']} value='{f['value']}'{extra}")
        print(f"\nFull text: {extras.get('text', '')[:500]}")

        with open("nutri_auto/form_structure_extras.json", "w", encoding="utf-8") as f:
            json.dump(extras, f, indent=2, ensure_ascii=False)

    page.screenshot(path="nutri_auto/debug_extras_loaded_screenshot.png", full_page=False)

finally:
    session.stop()
